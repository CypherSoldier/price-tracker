import json
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


HISTORY_FILE = Path(__file__).parent / "data" / "history.json"
LOGGER = logging.getLogger(__name__)

PROMPT = """
You are a market intelligence analyst. Given this week's price changes below,
write a concise 3-5 sentence summary highlighting price drops, price increases,
and new or removed items. Be specific with numbers. If this is the initial
snapshot, state that there is no prior snapshot for comparison.

Changes: {changes_json}
"""


def _price_value(price):
	"""Convert a displayed price (for example, '$12.34') to Decimal."""
	value = re.sub(r"[^\d.\-]", "", str(price).replace(",", ""))
	try:
		return Decimal(value)
	except InvalidOperation:
		return None


def _products_by_key(snapshot):
	products = {}
	for store in snapshot:
		source = store.get("source", "Unknown source")
		for product in store.get("products", []):
			name = product.get("name")
			if name is not None:
				products[(source, name)] = product.get("price", "")
	return products


def _load_history(history_path):
	path = Path(history_path)
	if not path.exists() or not path.read_text(encoding="utf-8").strip():
		return None
	with path.open(encoding="utf-8") as history_file:
		return json.load(history_file)


def _make_changes(current, previous):
	current_products = _products_by_key(current)
	if previous is None:
		return [
			{
				"source": source,
				"item": name,
				"change": "new",
				"old_price": None,
				"new_price": price,
			}
			for (source, name), price in current_products.items()
		]

	previous_products = _products_by_key(previous)
	changes = []
	for key, new_price in current_products.items():
		source, name = key
		if key not in previous_products:
			changes.append({
				"source": source,
				"item": name,
				"change": "new",
				"old_price": None,
				"new_price": new_price,
			})
			continue

		old_price = previous_products[key]
		old_value = _price_value(old_price)
		new_value = _price_value(new_price)
		if old_value is None or new_value is None:
			changed = str(old_price) != str(new_price)
		else:
			changed = old_value != new_value
		if not changed:
			continue

		change = "price_changed"
		change_amount = None
		percent_change = None
		if old_value is not None and new_value is not None:
			change_amount = float(new_value - old_value)
			if new_value < old_value:
				change = "price_drop"
			elif new_value > old_value:
				change = "price_increase"
			if old_value != 0:
				percent_change = float((new_value - old_value) / old_value * 100)

		changes.append({
			"source": source,
			"item": name,
			"change": change,
			"old_price": old_price,
			"new_price": new_price,
			"change_amount": change_amount,
			"percent_change": percent_change,
		})

	for (source, name), old_price in previous_products.items():
		if (source, name) not in current_products:
			changes.append({
				"source": source,
				"item": name,
				"change": "removed",
				"old_price": old_price,
				"new_price": None,
			})
	return changes


def _fallback_summary(changes, initial_snapshot):
	if initial_snapshot:
		return (
			f"This is the initial snapshot, so there are no prior prices for comparison. "
			f"Started tracking {len(changes)} products across the available sources."
		)
	if not changes:
		return "No product price or availability changes were detected since the previous snapshot."

	labels = {
		"price_drop": "price drops",
		"price_increase": "price increases",
		"new": "new items",
		"removed": "removed items",
		"price_changed": "other price changes",
	}
	counts = {}
	for entry in changes:
		counts[entry["change"]] = counts.get(entry["change"], 0) + 1
	overview = ", ".join(
		f"{count} {labels[kind]}"
		for kind, count in counts.items()
	)
	examples = []
	for entry in changes[:4]:
		if entry["change"] == "price_drop":
			detail = f"fell from {entry['old_price']} to {entry['new_price']}"
		elif entry["change"] == "price_increase":
			detail = f"rose from {entry['old_price']} to {entry['new_price']}"
		elif entry["change"] == "new":
			detail = f"was added at {entry['new_price']}"
		elif entry["change"] == "removed":
			detail = "is no longer listed"
		else:
			detail = f"changed from {entry['old_price']} to {entry['new_price']}"
		examples.append(f"{entry['item']} ({entry['source']}) {detail}")
	return f"Detected {overview}. " + "; ".join(examples) + "."


def _generate_summary(changes, initial_snapshot):
	api_key = os.getenv("GEMINI_API_KEY")
	fallback = _fallback_summary(changes, initial_snapshot)
	if not api_key:
		return fallback

	payload = {
		"initial_snapshot": initial_snapshot,
		"changes": changes,
	}
	try:
		from google import genai
		from google.genai import types

		with genai.Client(api_key=api_key) as client:
			response = client.models.generate_content(
				model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
				contents=PROMPT.format(
					changes_json=json.dumps(payload, ensure_ascii=False)
				),
				config=types.GenerateContentConfig(
					automatic_function_calling=(
						types.AutomaticFunctionCallingConfig(disable=True)
					)
				),
			)
		text = getattr(response, "text", None)
		return text.strip() if text and text.strip() else fallback
	except Exception as exc:
		# Keep reports available if the optional AI service is unavailable.
		error_message = str(exc).replace(api_key, "[REDACTED]")
		LOGGER.warning(
			"Gemini summary failed (%s): %s; using the local summary instead.",
			type(exc).__name__,
			error_message,
		)
		return fallback


def diff_and_summarize(current, history_path=HISTORY_FILE):
	"""Compare the current scrape with saved history and summarize changes."""
	previous = _load_history(history_path)
	changes = _make_changes(current, previous)
	summary = _generate_summary(changes, initial_snapshot=previous is None)
	return summary, changes


def save_history(current, history_path=HISTORY_FILE):
	"""Persist a successful scrape, replacing the previous snapshot atomically."""
	path = Path(history_path)
	path.parent.mkdir(parents=True, exist_ok=True)
	temporary_path = path.with_suffix(path.suffix + ".tmp")
	with temporary_path.open("w", encoding="utf-8") as history_file:
		json.dump(current, history_file, indent=2, ensure_ascii=False)
		history_file.write("\n")
	temporary_path.replace(path)