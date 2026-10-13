import logging
import os

from dotenv import load_dotenv
from scraper import scrape_all
from summarize import diff_and_summarize, save_history
from email_report import send_email, render_html

LOGGER = logging.getLogger(__name__)


def run():
    load_dotenv()
    gmail_user = os.getenv("GMAIL_USER")
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
    to_addr = os.getenv("EMAIL_TO") or gmail_user
    missing = [
        name
        for name, value in (
            ("GMAIL_USER", gmail_user),
            ("GMAIL_APP_PASSWORD", gmail_app_password),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )

    LOGGER.info("Scraping configured product pages.")
    current = scrape_all()
    source_count = len(current)
    product_count = sum(len(source.get("products", [])) for source in current)
    LOGGER.info(
        "Scrape complete: %d source pages, %d products.",
        source_count,
        product_count,
    )

    summary, changes = diff_and_summarize(current)
    LOGGER.info("Summary ready: %d detected changes.", len(changes))
    html = render_html(summary, changes)
    LOGGER.info("Sending report to %s.", to_addr)
    send_email(
        html,
        to_addr=to_addr,
        gmail_user=gmail_user,
        gmail_app_password=gmail_app_password,
    )
    LOGGER.info("Email accepted by SMTP; updating price history.")
    save_history(current)
    LOGGER.info("Price history updated successfully.")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        run()
    except Exception:
        LOGGER.exception("Price tracker run failed.")
        raise SystemExit(1) from None