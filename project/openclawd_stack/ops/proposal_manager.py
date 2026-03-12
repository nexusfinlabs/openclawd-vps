"""
proposal_manager.py — Canonical version (local + VPS)
Generates and sends professional proposals via OpenAI + SMTP.
All config from environment variables. No hardcoded values.
"""
import os
import sys
import smtplib
from email.message import EmailMessage


def load_env():
    """Load .env relative to this script's location."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k] = v.strip('"').strip("'")


def generate_proposal(dest, context):
    """Generate a proposal draft using OpenAI API."""
    prompt = f"""Actúa como asesor senior en desarrollo de proyectos, inversión e innovación empresarial.

Tu tarea es generar un email de propuesta profesional, claro y persuasivo basado en el siguiente contexto:

{context}

Reglas importantes:

1. El email debe ser totalmente original y específico al contexto proporcionado.
2. Nunca generes texto genérico tipo plantilla.
3. Utiliza la información proporcionada para crear una narrativa coherente del proyecto.
4. Si hay ubicación geográfica, intégrala de forma natural.
5. Si hay un objetivo (inversión, partnership, desarrollo, etc.), enfatízalo.
6. Usa un tono profesional, inteligente y natural.
7. Longitud aproximada: 120-180 palabras.
8. El email SIEMPRE debe terminar con esta firma exacta:

Alberto L.
Tech Advisor
dealflow@nexusfinlabs.com

Formato obligatorio de salida:

Subject 1:
Subject 2:
Subject 3:

---BODY---

(email completo con la firma)
"""

    try:
        from openai import OpenAI
        client = OpenAI()
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional deal advisor."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"Error generating proposal: {e}"


def send_proposal(to_email, body):
    """Send a proposal email using SMTP from env vars."""
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.ionos.es")
    smtp_port = int(os.environ.get("SMTP_PORT", 465))
    smtp_user = os.environ.get("EMAIL_SENDER", "dealflow@nexusfinlabs.com")
    smtp_password = os.environ.get("EMAIL_PASSWORD", "")
    smtp_bcc = os.environ.get("SMTP_BCC", "")

    if not smtp_password:
        return "ERROR: EMAIL_PASSWORD not found in .env"

    # Extract Subject 1 from body
    subject = "Business Proposal"
    clean_body_lines = []
    found_separator = False

    for line in body.split("\n"):
        if not found_separator:
            if "---BODY---" in line:
                found_separator = True
                continue
            if "Subject 1:" in line or "Asunto 1:" in line:
                subject = line.replace("Subject 1:", "").replace("Asunto 1:", "").strip()
        else:
            clean_body_lines.append(line)

    if not found_separator:
        clean_body_lines = [
            l for l in body.split("\n")
            if not l.strip().startswith(("Subject", "Asunto"))
        ]

    final_body = "\n".join(clean_body_lines).strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Alberto L. <{smtp_user}>"
    msg["To"] = to_email
    if smtp_bcc:
        msg["Bcc"] = smtp_bcc
    msg.set_content(final_body)

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
        return f"SUCCESS: Proposal sent to {to_email}"
    except Exception as e:
        return f"ERROR: Failed to send email: {e}"


if __name__ == "__main__":
    load_env()

    if len(sys.argv) < 2:
        print("Usage: proposal_manager.py --make|--send ...")
        sys.exit(1)

    action = sys.argv[1]

    if action == "--make":
        if len(sys.argv) < 4:
            print("ERROR: Missing arguments. Usage: --make 'dest' 'context'")
            sys.exit(1)
        draft = generate_proposal(sys.argv[2], sys.argv[3])
        print(draft)

    elif action == "--send":
        dest = sys.argv[2].replace("\u201c", "").replace("\u201d", "").replace('"', "").replace("'", "").strip()
        file_path = sys.argv[3]
        if os.path.exists(file_path):
            with open(file_path) as f:
                content = f.read()
            result = send_proposal(dest, content)
            print(result)
        else:
            print(f"ERROR: File {file_path} not found.")
