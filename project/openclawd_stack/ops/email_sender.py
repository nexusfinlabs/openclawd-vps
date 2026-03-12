import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import argparse
import sys

def send_email(to_email, subject, body_html, persona="M&A_Financial"):
    """
    Sends an email using the correct IONOS credentials based on the persona.
    """
    # Load env vars safely if not loaded
    env_path = '/home/albi_agent/openclawd_stack/.env'
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v.strip('"\'')

    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.ionos.es')
    smtp_port = int(os.environ.get('SMTP_PORT', 465))
    
    # Determine credentials and sender based on persona
    if persona == "Sales_Marketing":
        sender_email = "sales@iagrowth.io"
        sender_password = os.environ.get('EMAIL_PASS_IAGROWTH')
    else:
        # Default M&A Financial
        sender_email = "hola@nexusfinlabs.com"
        sender_password = os.environ.get('EMAIL_PASS_NEXUS')

    if not all([smtp_server, sender_email, sender_password]):
        print(f"Error: Missing SMTP credentials in .env for {sender_email}")
        sys.exit(1)

    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = to_email
    message['Subject'] = subject

    message.attach(MIMEText(body_html, 'html'))

    try:
        # Secure SSL connection
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender_email, sender_password)
        server.send_message(message)
        server.quit()
        print(f"Sent email to {to_email} successfully from {sender_email}.")
    except Exception as e:
        print(f"Failed to send email to {to_email} from {sender_email}: {e}")
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Send an approved draft email")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body", required=True, help="HTML body content")
    parser.add_argument("--persona", default="M&A_Financial", help="Persona (M&A_Financial or Sales_Marketing)")
    
    args = parser.parse_args()
    send_email(args.to, args.subject, args.body, args.persona)
