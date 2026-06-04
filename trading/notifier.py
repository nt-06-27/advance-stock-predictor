import imaplib
import logging
import os
import re
import smtplib
import email
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _load_email_config() -> Optional[dict]:
    """Read email config from environment. Returns None if not configured."""
    server = os.getenv("EMAIL_SMTP_SERVER")
    port = os.getenv("EMAIL_SMTP_PORT")
    username = os.getenv("EMAIL_USERNAME")
    password = os.getenv("EMAIL_PASSWORD")
    from_addr = os.getenv("EMAIL_FROM") or username
    to_addr = os.getenv("EMAIL_TO")

    if not all([server, port, username, password, to_addr]):
        return None

    return {
        "server": server,
        "port": int(port),
        "username": username,
        "password": password,
        "from": from_addr,
        "to": to_addr,
    }


def send_weekly_report(report: dict, formatted: str) -> bool:
    """Send the weekly P&L report via email/SMS, asking YES or NO.

    Returns True if sent successfully, False if email not configured or failed.
    """
    cfg = _load_email_config()
    if cfg is None:
        logger.info("[NOTIFY] Email not configured — skipping notification")
        return False

    pnl = report.get("pnl", 0)
    direction = "UP" if pnl >= 0 else "DOWN"
    subject = f"[Autopilot] Week {report['iso_week']}: {direction} ${pnl:>+.2f} ({report['pnl_percent']:>+.2f}%)"

    # Compact body that fits in SMS (the detailed report is separate)
    body = (
        f"Week {report['iso_week']} complete.\n"
        f"P&L: ${pnl:>+.2f} ({report['pnl_percent']:>+.2f}%)\n"
        f"Equity: ${report['start_equity']:,.0f} -> ${report['end_equity']:,.0f}\n"
        f"Trades: {report['trade_count']}\n"
        f"Best: {report['best_ticker']} ({report['best_return']:>+.2f}%)\n"
        f"Worst: {report['worst_ticker']} ({report['worst_return']:>+.2f}%)\n"
        f"\n"
        f"Reply YES to continue trading next week.\n"
        f"Reply NO to stop until you run --approve."
    )

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]

    try:
        with smtplib.SMTP(cfg["server"], cfg["port"]) as smtp:
            smtp.starttls()
            smtp.login(cfg["username"], cfg["password"])
            smtp.send_message(msg)
        logger.info("[NOTIFY] Weekly SMS sent to %s", cfg["to"])
        return True
    except Exception as e:
        logger.warning("[NOTIFY] Failed to send SMS: %s", e)
        return False


def send_approval_reminder() -> bool:
    """Resend the approval request as a reminder."""
    cfg = _load_email_config()
    if cfg is None:
        return False

    body = (
        "Reminder: No reply yet.\n\n"
        "Reply YES to continue trading next week.\n"
        "Reply NO to stop until you run --approve."
    )

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = "[Autopilot] Approval still needed"
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]

    try:
        with smtplib.SMTP(cfg["server"], cfg["port"]) as smtp:
            smtp.starttls()
            smtp.login(cfg["username"], cfg["password"])
            smtp.send_message(msg)
        logger.info("[NOTIFY] Approval reminder sent to %s", cfg["to"])
        return True
    except Exception as e:
        logger.warning("[NOTIFY] Failed to send approval reminder: %s", e)
        return False


def check_sms_reply() -> Optional[bool]:
    """Check Gmail inbox for YES/NO reply to the autopilot SMS.

    Returns:
        True  if YES reply found (approve next week)
        False if NO reply found (stop trading)
        None  if no reply found yet
    """
    cfg = _load_email_config()
    if cfg is None:
        return None

    try:
        # Connect to Gmail via IMAP
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(cfg["username"], cfg["password"])
        mail.select("INBOX")

        # Search for replies from the last 2 days
        since_date = (datetime.now(tz=timezone.utc) - timedelta(days=2)).strftime("%d-%b-%Y")
        status, messages = mail.search(None, f'(SINCE {since_date})')
        if status != "OK":
            return None

        msg_ids = messages[0].split()
        logger.debug("[NOTIFY] Checking %d recent emails for reply", len(msg_ids))

        for mid in reversed(msg_ids[-20:]):  # Check last 20 emails (newest first)
            status, data = mail.fetch(mid, "(BODY[TEXT])")
            if status != "OK":
                continue

            raw_body = data[0][1].decode("utf-8", errors="ignore").strip()
            if not raw_body:
                continue

            # Fetch subject too
            status, subj_data = mail.fetch(mid, "(BODY[HEADER.FIELDS (SUBJECT)])")
            subject = ""
            if status == "OK":
                subj_raw = subj_data[0][1].decode("utf-8", errors="ignore").strip()
                if "Subject:" in subj_raw:
                    subject = subj_raw.split("Subject:")[1].strip()

            # Look for YES/NO in body (allow some surrounding whitespace/punctuation)
            body_clean = raw_body.strip().lower()
            # Check for standalone "yes" or "no" in the body
            if re.search(r'\byes\b', body_clean):
                logger.info("[NOTIFY] Found YES reply (subject: %s)", subject)
                mail.logout()
                return True
            if re.search(r'\bno\b', body_clean):
                logger.info("[NOTIFY] Found NO reply (subject: %s)", subject)
                mail.logout()
                return False

        mail.logout()
        return None

    except imaplib.IMAP4.error as e:
        logger.warning("[NOTIFY] IMAP login failed: %s", e)
        return None
    except Exception as e:
        logger.warning("[NOTIFY] Failed to check for replies: %s", e)
        return None
