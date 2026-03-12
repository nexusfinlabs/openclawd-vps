import sys
import os
import smtplib
from email.message import EmailMessage
from sqlalchemy import create_engine, text
from db import DATABASE_URL

def main():
    if len(sys.argv) < 2:
        print("Usage: python email_sender.py <draft_id>")
        sys.exit(1)

    draft_id = sys.argv[1]

    # SMTP config
    SMTP_SERVER = "smtp.ionos.es"  # Update if IONOS requires a different URL
    SMTP_PORT = 465 # SSL
    SMTP_USER = "dealflow@nexusfinlabs.com"
    SMTP_PASS = os.environ.get("IONOS_SMTP_PASSWORD")

    if not SMTP_PASS:
        print("ERROR: IONOS_SMTP_PASSWORD is not set in environment.")
        sys.exit(1)

    # Fetch from DB
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        query = text("SELECT target_email, subject, body, status FROM email_drafts WHERE id = :id FOR UPDATE")
        result = conn.execute(query, {"id": draft_id}).fetchone()

        if not result:
            print(f"ERROR: Draft {draft_id} not found.")
            sys.exit(1)

        target, subject, body, status = result
        if status == 'sent':
            print(f"ERROR: Draft {draft_id} was already sent.")
            sys.exit(1)

        # Send Email
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = f"Nexus Finlabs <{SMTP_USER}>"
        msg['To'] = target

        try:
            print(f"Connecting to {SMTP_SERVER} to send email ID {draft_id} to {target}...")
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)

            # Update status
            upd = text("UPDATE email_drafts SET status = 'sent', sent_at = NOW() WHERE id = :id")
            conn.execute(upd, {"id": draft_id})
            conn.commit()

            print(f"SUCCESS: Email {draft_id} sent successfully!")
        except Exception as e:
            print(f"ERROR sending email: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
