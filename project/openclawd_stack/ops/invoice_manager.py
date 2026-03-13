#!/usr/bin/env python3
"""
Invoice Manager — Generate and send professional invoices via WhatsApp/Telegram.

Usage:
  python3 invoice_manager.py make "5000 EUR consulting para TechCorp"
  python3 invoice_manager.py send "last"

Features:
  - Client DB (JSON) — stores client data for reuse
  - LLM enrichment — looks up new client info via OpenRouter
  - Sequential numbering (OC-FRA003+)
  - PDF generation via WeasyPrint + Jinja2 template
  - Asks for confirmation of new client data before generating
"""

import json
import os
import re
import sys
import subprocess
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ──────────────────────────────────────────────
TEMPLATE_DIR = "/home/albi_agent/openclawd_stack/app/templates"
DRAFTS_DIR = "/home/albi_agent/.openclaw/workspace/docs/drafts"
CLIENT_DB_PATH = "/home/albi_agent/openclawd_stack/data/clients.json"
INVOICE_COUNTER_PATH = "/home/albi_agent/openclawd_stack/data/invoice_counter.json"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/invoice_manager.log"),
    ],
)
log = logging.getLogger("invoice_manager")


def load_env():
    """Load .env if available."""
    for path in ["/home/albi_agent/openclawd_stack/.env", ".env"]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k, v.strip("\"'"))
    global OPENROUTER_API_KEY
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")


# ── Client DB ───────────────────────────────────────────
def load_clients():
    os.makedirs(os.path.dirname(CLIENT_DB_PATH), exist_ok=True)
    if os.path.exists(CLIENT_DB_PATH):
        with open(CLIENT_DB_PATH) as f:
            return json.load(f)
    return {}


def save_clients(clients):
    os.makedirs(os.path.dirname(CLIENT_DB_PATH), exist_ok=True)
    with open(CLIENT_DB_PATH, "w") as f:
        json.dump(clients, f, indent=2, ensure_ascii=False)


def find_client(name):
    """Find a client by name (case-insensitive partial match)."""
    clients = load_clients()
    name_lower = name.lower().strip()
    for key, data in clients.items():
        if name_lower in key.lower() or name_lower in data.get("name", "").lower():
            return data
    return None


def save_client(client_data):
    clients = load_clients()
    key = client_data["name"].lower().strip()
    clients[key] = client_data
    save_clients(clients)
    log.info("Client saved to DB: %s", client_data["name"])


# ── Invoice Counter ─────────────────────────────────────
def get_next_invoice_number():
    os.makedirs(os.path.dirname(INVOICE_COUNTER_PATH), exist_ok=True)
    if os.path.exists(INVOICE_COUNTER_PATH):
        with open(INVOICE_COUNTER_PATH) as f:
            data = json.load(f)
    else:
        data = {"last_number": 2}  # Start at 3

    data["last_number"] += 1
    num = data["last_number"]

    with open(INVOICE_COUNTER_PATH, "w") as f:
        json.dump(data, f)

    return f"OC-FRA{num:03d}"


# ── LLM Client Enrichment ──────────────────────────────
def enrich_client_via_llm(company_name, context=""):
    """Use LLM to find company details for invoicing."""
    if not OPENROUTER_API_KEY:
        log.warning("No OPENROUTER_API_KEY — cannot enrich client")
        return None

    prompt = f"""Necesito los datos de facturación de la empresa "{company_name}".
{f'Contexto adicional: {context}' if context else ''}

Devuelve SOLO un JSON válido con estos campos:
{{
  "name": "Nombre legal completo de la empresa",
  "id_label": "CIF o NIF o VAT",
  "id_value": "número fiscal",
  "address": "dirección completa",
  "city": "código postal, ciudad, país",
  "email": "email de contacto si lo conoces, sino vacío"
}}

Si no estás seguro de algún dato, pon "VERIFICAR" como valor.
Responde SOLO con el JSON, sin explicaciones."""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=30,
        )
        content = resp.json()["choices"][0]["message"]["content"]

        # Extract JSON from response
        json_match = re.search(r'\{[^{}]+\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        log.error("LLM enrichment failed: %s", e)

    return None


# ── Parse User Input ────────────────────────────────────
def parse_invoice_request(text):
    """Parse natural language invoice request into structured data.

    Examples:
      '5000 consulting para TechCorp'
      '3000 EUR advisory mensual para Stripe, contacto john@stripe.com'
      '1500 desarrollo web para NovaPay, 2 meses'
    """
    if not OPENROUTER_API_KEY:
        log.warning("No OPENROUTER_API_KEY — using basic parsing")
        return _basic_parse(text)

    prompt = f"""Analiza esta solicitud de factura y extrae los datos.
Solicitud: "{text}"

Devuelve SOLO un JSON válido:
{{
  "client_name": "nombre de la empresa cliente",
  "amount": 0.00,
  "currency": "EUR",
  "description": "descripción del servicio",
  "quantity": 1,
  "notes": "notas adicionales o vacío",
  "client_email": "email del cliente si se menciona, sino vacío"
}}

Responde SOLO con el JSON."""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=30,
        )
        content = resp.json()["choices"][0]["message"]["content"]
        json_match = re.search(r'\{[^{}]+\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        log.error("LLM parse failed: %s", e)

    return _basic_parse(text)


def _basic_parse(text):
    """Fallback basic parser."""
    amount_match = re.search(r'(\d+(?:\.\d+)?)', text)
    amount = float(amount_match.group(1)) if amount_match else 0

    para_match = re.search(r'para\s+(.+?)(?:\s*,|\s*$)', text, re.IGNORECASE)
    client = para_match.group(1).strip() if para_match else "CLIENTE_DESCONOCIDO"

    desc = re.sub(r'\d+(?:\.\d+)?\s*(?:EUR|€)?\s*', '', text).strip()
    desc = re.sub(r'para\s+.+', '', desc, flags=re.IGNORECASE).strip()

    return {
        "client_name": client,
        "amount": amount,
        "currency": "EUR",
        "description": desc or "Servicios profesionales de consultoría",
        "quantity": 1,
        "notes": "",
        "client_email": "",
    }


# ── PDF Generation ──────────────────────────────────────
def generate_invoice_pdf(invoice_data):
    """Generate PDF from invoice data using Jinja2 + WeasyPrint."""
    from jinja2 import Environment, FileSystemLoader
    from weasyprint import HTML

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("factura.html")

    html_content = template.render(**invoice_data)

    os.makedirs(DRAFTS_DIR, exist_ok=True)
    inv_num = invoice_data["invoice_number"]
    pdf_path = os.path.join(DRAFTS_DIR, f"{inv_num}.pdf")

    HTML(string=html_content).write_pdf(pdf_path)
    log.info("PDF generated: %s", pdf_path)

    return pdf_path


# ── Main Commands ───────────────────────────────────────
def make_invoice(user_text):
    """Main flow: parse request → find/enrich client → generate PDF."""

    # 1. Parse request
    log.info("Parsing invoice request: %s", user_text[:100])
    parsed = parse_invoice_request(user_text)
    client_name = parsed.get("client_name", "")
    amount = float(parsed.get("amount", 0))
    description = parsed.get("description", "Servicios profesionales")

    if not client_name or amount <= 0:
        return "❌ No pude entender la solicitud. Formato: `!make-invoice 5000 consulting para TechCorp`"

    # 2. Find or enrich client
    client = find_client(client_name)
    if client:
        log.info("Client found in DB: %s", client["name"])
        client_status = f"📋 Cliente encontrado en DB: {client['name']}"
    else:
        log.info("Client NOT in DB, enriching via LLM: %s", client_name)
        enriched = enrich_client_via_llm(client_name)
        if enriched:
            client = enriched
            # Add email from parsed request if LLM didn't find it
            if parsed.get("client_email") and not client.get("email"):
                client["email"] = parsed["client_email"]
            save_client(client)
            client_status = f"🔍 Cliente nuevo (LLM): {client['name']}\n⚠️ Verifica los datos antes de enviar"
        else:
            client = {
                "name": client_name,
                "id_label": "CIF",
                "id_value": "VERIFICAR",
                "address": "VERIFICAR",
                "city": "VERIFICAR",
                "email": parsed.get("client_email", ""),
            }
            save_client(client)
            client_status = f"⚠️ Cliente nuevo sin datos: {client_name}\n⚠️ VERIFICA los datos antes de enviar"

    # 3. Generate invoice
    inv_number = get_next_invoice_number()
    today = datetime.now()
    due_date = today + timedelta(days=30)

    subtotal = amount
    iva_pct = 21
    irpf_pct = 15
    iva_amount = subtotal * iva_pct / 100
    irpf_amount = subtotal * irpf_pct / 100
    total = subtotal + iva_amount - irpf_amount

    invoice_data = {
        "invoice_number": inv_number,
        "invoice_date": today.strftime("%d/%m/%Y"),
        "due_date": due_date.strftime("%d/%m/%Y"),
        "client_name": client.get("name", client_name),
        "client_id_label": client.get("id_label", "CIF"),
        "client_id": client.get("id_value", ""),
        "client_address": client.get("address", ""),
        "client_city": client.get("city", ""),
        "client_email": client.get("email", ""),
        "items": [
            {
                "description": description,
                "quantity": parsed.get("quantity", 1),
                "unit_price": amount,
                "total": amount,
            }
        ],
        "subtotal": subtotal,
        "iva_pct": iva_pct,
        "iva_amount": iva_amount,
        "irpf_pct": irpf_pct,
        "irpf_amount": irpf_amount,
        "total": total,
        "payment_method": "Transferencia bancaria",
        "iban": os.environ.get("IBAN", ""),
        "notes": parsed.get("notes", ""),
    }

    # Save draft data for send-invoice
    draft_path = os.path.join(DRAFTS_DIR, f"{inv_number}_data.json")
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    with open(draft_path, "w") as f:
        json.dump(invoice_data, f, indent=2, ensure_ascii=False)

    try:
        pdf_path = generate_invoice_pdf(invoice_data)
    except Exception as e:
        log.error("PDF generation failed: %s", e)
        return f"❌ Error generando PDF: {str(e)[:200]}"

    result = (
        f"📄 *Factura generada: {inv_number}*\n\n"
        f"👤 *Cliente:* {client.get('name', client_name)}\n"
        f"   {client.get('id_label', 'CIF')}: {client.get('id_value', 'N/A')}\n"
        f"   {client.get('address', '')}\n\n"
        f"💰 *Importe:*\n"
        f"   Subtotal: {subtotal:,.2f} €\n"
        f"   IVA ({iva_pct}%): +{iva_amount:,.2f} €\n"
        f"   IRPF ({irpf_pct}%): -{irpf_amount:,.2f} €\n"
        f"   *TOTAL: {total:,.2f} €*\n\n"
        f"📋 {client_status}\n\n"
        f"📎 PDF: {pdf_path}\n\n"
        f"Para enviar: `!send-invoice {inv_number}`"
    )

    return result


def send_invoice(invoice_ref):
    """Send a previously generated invoice PDF via email."""
    invoice_ref = invoice_ref.strip()

    # Find the latest invoice if "last" or empty
    if not invoice_ref or invoice_ref.lower() == "last":
        # Find the most recent PDF in drafts
        drafts = Path(DRAFTS_DIR)
        pdfs = sorted(drafts.glob("OC-FRA*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not pdfs:
            return "❌ No hay facturas pendientes. Usa `!make-invoice` primero."
        invoice_ref = pdfs[0].stem

    pdf_path = os.path.join(DRAFTS_DIR, f"{invoice_ref}.pdf")
    data_path = os.path.join(DRAFTS_DIR, f"{invoice_ref}_data.json")

    if not os.path.exists(pdf_path):
        return f"❌ Factura {invoice_ref} no encontrada en {DRAFTS_DIR}"

    # Load invoice data
    if os.path.exists(data_path):
        with open(data_path) as f:
            inv_data = json.load(f)
        client_email = inv_data.get("client_email", "")
        client_name = inv_data.get("client_name", "")
        inv_total = inv_data.get("total", 0)
    else:
        client_email = ""
        client_name = "Cliente"
        inv_total = 0

    if not client_email:
        return (
            f"⚠️ Factura {invoice_ref} no tiene email del cliente.\n"
            f"Envía: `!send-invoice {invoice_ref} email@cliente.com`"
        )

    # Send via email (use SMTP)
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.application import MIMEApplication

        sender = "dealflow@nexusfinlabs.com"
        password = os.environ.get("EMAIL_PASSWORD", "")

        msg = MIMEMultipart()
        msg["From"] = f"Alberto Lebrón <{sender}>"
        msg["To"] = client_email
        msg["Subject"] = f"Factura {invoice_ref} — Alberto Lebrón / Nexus FinLabs"

        body = f"""Estimado/a {client_name},

Adjunto la factura {invoice_ref} por un importe de {inv_total:,.2f} €.

Quedo a su disposición para cualquier consulta.

Un saludo,
Alberto Jesús Lebrón Lobo
dealflow@nexusfinlabs.com
"""
        msg.attach(MIMEText(body, "plain"))

        with open(pdf_path, "rb") as f:
            attachment = MIMEApplication(f.read(), _subtype="pdf")
            attachment.add_header("Content-Disposition", "attachment", filename=f"{invoice_ref}.pdf")
            msg.attach(attachment)

        with smtplib.SMTP_SSL("smtp.ionos.es", 465) as server:
            server.login(sender, password)
            server.send_message(msg)

        return (
            f"✅ *Factura {invoice_ref} enviada*\n\n"
            f"📧 Destinatario: {client_email}\n"
            f"💰 Total: {inv_total:,.2f} €\n"
            f"📎 PDF adjunto"
        )

    except Exception as e:
        log.error("Email send failed: %s", e)
        return f"❌ Error enviando factura: {str(e)[:200]}"


# ── CLI Entry Point ─────────────────────────────────────
if __name__ == "__main__":
    load_env()

    if len(sys.argv) < 2:
        print("Usage: python3 invoice_manager.py make|send <args>")
        sys.exit(1)

    action = sys.argv[1].lower()
    args = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""

    if action == "make":
        result = make_invoice(args)
    elif action == "send":
        result = send_invoice(args)
    else:
        result = f"❌ Acción desconocida: {action}. Usa 'make' o 'send'."

    print(result)
