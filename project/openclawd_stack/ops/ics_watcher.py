#!/usr/bin/env python3
"""
ICS Email Watcher — Automatically adds calendar events from incoming emails.

Polls IMAP inbox (dealflow@nexusfinlabs.com) every 5 minutes for new emails
with .ics attachments. When found, extracts the ICS and adds the event to
Google Calendar. Sends a WhatsApp/Telegram notification on success.

Runs as a systemd service: ics-watcher.service
"""

import os
import sys
import time
import email
import imaplib
import json
import subprocess
import logging
from datetime import datetime
from email.header import decode_header

# Add parent dir for calendar_manager import
sys.path.insert(0, os.path.dirname(__file__))
from calendar_manager import parse_ics_and_add_to_calendar

# ── Config ──────────────────────────────────────────────
POLL_INTERVAL = 300  # 5 minutes
PROCESSED_FILE = "/tmp/ics_watcher_processed.json"

IMAP_CONFIG = {
    "email": "dealflow@nexusfinlabs.com",
    "imap_server": "imap.ionos.es",
}

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/ics_watcher.log"),
    ],
)
log = logging.getLogger("ics_watcher")


def load_env():
    """Load .env if available."""
    for path in ["/home/albi_agent/openclawd_stack/.env", ".env"]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k, v.strip("\"'"))


def load_processed():
    """Load set of already-processed email UIDs."""
    try:
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE) as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()


def save_processed(uids):
    """Save processed UIDs (keep last 500 to prevent unbounded growth)."""
    trimmed = list(uids)[-500:]
    with open(PROCESSED_FILE, "w") as f:
        json.dump(trimmed, f)


def send_notification(message):
    """Send WhatsApp notification via openclaw CLI."""
    try:
        env = os.environ.copy()
        env["PATH"] = f"/home/albi_agent/.nvm/versions/node/v22.22.0/bin:{env.get('PATH', '')}"
        subprocess.run(
            [
                "openclaw", "message", "send",
                "--channel", "whatsapp",
                "--target", "34605693177",
                "--message", message,
            ],
            timeout=30,
            env=env,
            capture_output=True,
        )
    except Exception as e:
        log.error("Failed to send notification: %s", e)


def decode_subject(msg):
    """Decode email subject safely."""
    raw = msg.get("subject", "(sin asunto)")
    try:
        parts = decode_header(raw)
        return "".join(
            str(t[0], t[1] or "utf-8") if isinstance(t[0], bytes) else t[0]
            for t in parts
        )
    except Exception:
        return raw


def check_inbox():
    """Connect to IMAP, find new emails with .ics, add to Google Calendar."""
    password = os.environ.get("EMAIL_PASSWORD", "")
    if not password:
        log.error("EMAIL_PASSWORD not set — skipping check")
        return

    processed = load_processed()
    new_events = 0

    try:
        log.info("Connecting to %s ...", IMAP_CONFIG["imap_server"])
        mail = imaplib.IMAP4_SSL(IMAP_CONFIG["imap_server"])
        mail.login(IMAP_CONFIG["email"], password)
        mail.select("inbox")

        # Search for emails with calendar content (UNSEEN first, then recent)
        _, unseen_nums = mail.search(None, "UNSEEN")
        _, recent_nums = mail.search(None, "(SINCE 01-Mar-2026)")

        # Combine and deduplicate, prioritize unseen
        all_nums = set()
        for nums in [unseen_nums[0].split(), recent_nums[0].split()[-20:]]:
            all_nums.update(nums)

        log.info("Checking %d emails for .ics attachments...", len(all_nums))

        for num in sorted(all_nums):
            uid_key = num.decode() if isinstance(num, bytes) else str(num)

            if uid_key in processed:
                continue

            _, data = mail.fetch(num, "(RFC822)")
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = decode_subject(msg)
            sender = msg.get("from", "unknown")

            for part in msg.walk():
                content_type = part.get_content_type()
                filename = part.get_filename() or ""
                disposition = str(part.get("Content-Disposition", ""))

                is_ics = (
                    "text/calendar" in content_type
                    or (filename.endswith(".ics") and "attachment" in disposition)
                )

                if is_ics:
                    log.info("🗓️ Found ICS in email: '%s' from %s", subject[:60], sender)

                    ics_data = part.get_payload(decode=True)
                    ics_path = f"/tmp/auto_ics_{uid_key}.ics"

                    with open(ics_path, "wb") as f:
                        f.write(ics_data)

                    success = parse_ics_and_add_to_calendar(ics_path)

                    if success:
                        new_events += 1
                        log.info("✅ Event added to Google Calendar from: %s", subject[:60])

                        send_notification(
                            f"🗓️ *Evento añadido automáticamente*\n"
                            f"📧 De: {sender}\n"
                            f"📋 Asunto: {subject[:80]}\n"
                            f"✅ Agregado a Google Calendar"
                        )

                    # Clean up temp file
                    try:
                        os.remove(ics_path)
                    except OSError:
                        pass

                    break  # One ICS per email is enough

            # Mark as processed regardless of ICS presence
            processed.add(uid_key)

        mail.close()
        mail.logout()

    except Exception as e:
        log.error("IMAP error: %s", e)

    save_processed(processed)

    if new_events:
        log.info("Added %d new events this cycle", new_events)
    else:
        log.info("No new ICS events found")


def main():
    load_env()

    log.info("=" * 50)
    log.info("ICS Email Watcher started")
    log.info("Inbox: %s", IMAP_CONFIG["email"])
    log.info("Poll interval: %ds", POLL_INTERVAL)
    log.info("=" * 50)

    while True:
        try:
            check_inbox()
        except KeyboardInterrupt:
            log.info("Shutting down...")
            break
        except Exception as e:
            log.error("Unexpected error: %s", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
