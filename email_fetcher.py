import imaplib
import email
import os
import re
import smtplib
import subprocess
import sys
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from dotenv import load_dotenv
from ytel_downloader import download_report

# Load credentials from .env file
load_dotenv()

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
IMAP_SERVER   = "secure.emailsrvr.com"
IMAP_PORT     = 993
SMTP_SERVER   = "secure.emailsrvr.com"
SMTP_PORT     = 465
EMAIL_ADDRESS  = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

SUBJECT_KEYWORD  = "job confirmation"
SENDER_FILTER    = "no-reply@ytel.com"
REPORT_RECIPIENTS = [r.strip() for r in os.getenv("REPORT_RECIPIENTS", "").split(",") if r.strip()]

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
CSV_SAVE_PATH  = os.path.join(BASE_DIR, "ytel_agent_report.csv")
EXCEL_PATH     = os.path.join(BASE_DIR, "Formatted_Agent_Report.xlsx")
CSV_REPORT_PATH = os.path.join(BASE_DIR, "Formatted_Agent_Report.csv")
REPORT_SCRIPT  = os.path.join(BASE_DIR, "performancereport.py")
LOG_FILE       = os.path.join(BASE_DIR, "email_fetcher.log")
# ─────────────────────────────────────────────

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def decode_str(value):
    """Decode encoded email header strings."""
    parts = decode_header(value)
    decoded = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded += part.decode(enc or "utf-8", errors="replace")
        else:
            decoded += part
    return decoded

def fetch_csv_from_email():
    log("Connecting to Rackspace IMAP...")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    except Exception as e:
        log(f"ERROR: Could not connect/login — {e}")
        return False

    mail.select("inbox")

    # Search specifically for TODAY's emails from Ytel
    from email.utils import parsedate_to_datetime
    today_str = datetime.now().strftime("%d-%b-%Y")  # e.g. "15-Jun-2026"
    status, messages = mail.search(None, f'FROM "no-reply@ytel.com" SINCE {today_str}')
    if status != "OK" or not messages[0]:
        # Fall back to last 3 emails if none found today
        log("No emails from Ytel today, checking last 3...")
        status, messages = mail.search(None, 'FROM "no-reply@ytel.com"')
        if status != "OK" or not messages[0]:
            log("No emails from no-reply@ytel.com found.")
            mail.logout()
            return False
        email_ids = messages[0].split()[-3:]
    else:
        email_ids = messages[0].split()

    log(f"Found {len(email_ids)} email(s) from Ytel. Scanning most recent first...")

    found = False
    # Check newest emails first
    for eid in reversed(email_ids):
        status, msg_data = mail.fetch(eid, "(RFC822)")
        if status != "OK":
            continue

        msg = email.message_from_bytes(msg_data[0][1])
        subject = decode_str(msg.get("Subject", ""))
        sender  = decode_str(msg.get("From", ""))

        if SUBJECT_KEYWORD.lower() not in subject.lower():
            continue

        if SENDER_FILTER.lower() not in sender.lower():
            continue

        log(f"Matched email from '{sender}': '{subject}'")

        # Look for CSV attachment first, then fall back to download link in body
        csv_downloaded = False

        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                filename = decode_str(filename)
                if filename.lower().endswith(".csv"):
                    log(f"Downloading attachment: {filename}")
                    payload = part.get_payload(decode=True)
                    with open(CSV_SAVE_PATH, "wb") as f:
                        f.write(payload)
                    log(f"Saved CSV to: {CSV_SAVE_PATH}")
                    mail.store(eid, "+FLAGS", "\\Seen")
                    csv_downloaded = True
                    found = True
                    break

        # No attachment — extract the Report Data download link from HTML body
        if not csv_downloaded:
            html_body = None
            plain_body = None
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/html" and html_body is None:
                    html_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                elif ct == "text/plain" and plain_body is None:
                    plain_body = part.get_payload(decode=True).decode("utf-8", errors="replace")

            body = html_body or plain_body or ""
            urls = re.findall(r'https?://[^\s"\'<>]+', body)
            report_url = None
            for url in urls:
                if "ask.ytel.com/e3t" in url or (
                    "ytel.com" in url and any(
                        kw in url.lower() for kw in ["report", "download", "job", "csv", "export"]
                    )
                ):
                    report_url = url
                    break

            if report_url:
                log(f"Found report link: {report_url[:80]}...")
                if download_report(report_url, log_fn=log):
                    mail.store(eid, "+FLAGS", "\\Seen")
                    found = True
                    break  # Stop after first successful download
            else:
                log(f"WARNING: No report link found. Total URLs in email: {len(urls)}")

        if found:
            break

    mail.logout()

    if not found:
        log("No matching email with CSV attachment found.")

    return found

def send_report():
    recipients_str = ", ".join(REPORT_RECIPIENTS)
    log(f"Sending report to {recipients_str}...")
    if not os.path.exists(EXCEL_PATH):
        log("ERROR: Excel file not found, cannot send.")
        return False

    try:
        today = datetime.now().strftime("%B %d, %Y")
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_ADDRESS
        msg["To"]      = ", ".join(REPORT_RECIPIENTS)
        msg["Subject"] = f"Agent Performance Report — {today}"

        body = f"Hi,\n\nPlease find attached the Agent Performance Report for {today}.\n\nThis report was generated automatically.\n\nThanks,\nIconic Results"
        msg.attach(MIMEText(body, "plain"))

        with open(EXCEL_PATH, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=Agent_Performance_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx")
        msg.attach(part)

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, REPORT_RECIPIENTS, msg.as_string())

        log(f"Report sent successfully to {recipients_str}")
        return True

    except Exception as e:
        log(f"ERROR sending email: {e}")
        return False


def run_report():
    log("Running performance report script...")
    try:
        result = subprocess.run(
            [sys.executable, REPORT_SCRIPT],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(REPORT_SCRIPT)
        )
        if result.stdout:
            log(f"Report output: {result.stdout.strip()}")
        if result.returncode != 0:
            log(f"ERROR in report script: {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        log(f"ERROR running report: {e}")
        return False

if __name__ == "__main__":
    log("=" * 50)
    log("Starting Agent Performance Report auto-fetch")

    if fetch_csv_from_email():
        if run_report():
            log("Report generated successfully.")
            send_report()
        else:
            log("Report generation failed.")
    else:
        log("No CSV downloaded. Report not generated.")

    log("Done.")
