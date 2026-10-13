import smtplib
import logging
from html import escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

LOGGER = logging.getLogger(__name__)


def render_html(summary, changes):
    rows = []
    for change in changes:
        rows.append(
            "<tr>"
            f"<td>{escape(str(change.get('source', '')))}</td>"
            f"<td>{escape(str(change.get('item', '')))}</td>"
            f"<td>{escape(change.get('change', '').replace('_', ' ').title())}</td>"
            f"<td>{escape(str(change.get('old_price') or '—'))}</td>"
            f"<td>{escape(str(change.get('new_price') or '—'))}</td>"
            "</tr>"
        )
    table_rows = "".join(rows) or '<tr><td colspan="5">No changes detected.</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weekly Competitor Price Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; color: #1f2937; line-height: 1.5; }}
    main {{ max-width: 900px; margin: 24px auto; padding: 24px; }}
    h1 {{ color: #111827; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    .summary {{ background: #f9fafb; border-left: 4px solid #2563eb; padding: 12px 16px; }}
  </style>
</head>
<body>
  <main>
    <h1>Weekly Competitor Price Report</h1>
    <p class="summary">{escape(str(summary))}</p>
    <table>
      <thead><tr><th>Source</th><th>Product</th><th>Change</th><th>Previous price</th><th>Current price</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </main>
</body>
</html>"""


def send_email(html_content, to_addr, gmail_user, gmail_app_password):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Weekly Competitor Price Report"
    msg["From"] = gmail_user
    msg["To"] = to_addr
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        try:
            server.login(gmail_user, gmail_app_password)
        except smtplib.SMTPAuthenticationError as exc:
            raise RuntimeError(
                "Gmail rejected SMTP authentication. Set GMAIL_APP_PASSWORD to a "
                "valid Google app password (not the account password); app passwords "
                "require 2-Step Verification."
            ) from exc
        refused_recipients = server.sendmail(gmail_user, to_addr, msg.as_string())
        if refused_recipients:
            raise smtplib.SMTPRecipientsRefused(refused_recipients)

    LOGGER.info(
        "SMTP accepted the report for %s; check Spam/Promotions if it is missing.",
        to_addr,
    )