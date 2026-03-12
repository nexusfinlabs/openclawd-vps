#!/usr/bin/env python3
"""
Command Router — Local VPS command executor for OpenClaw.

Tails the OpenClaw gateway log file, detects incoming WhatsApp messages
starting with '!', and executes the corresponding bash scripts via subprocess.
Scripts handle their own response delivery via 'openclaw message send'.

Architecture:
  WhatsApp → Gateway → log file → THIS ROUTER → subprocess → scripts → openclaw message send

No HTTP server. No cloud agent. No approvals. 100% local.
"""

import json
import os
import re
import subprocess
import sys
import time
import logging
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────
SKILLS_DIR = "/home/albi_agent/openclawd_stack/ops/openclaw_skills"
WORK_DIR = "/home/albi_agent/openclawd_stack"
LOG_DIR = "/tmp/openclaw"
ALLOWED_NUMBERS = {"+34605693177"}
SUBPROCESS_TIMEOUT = 120  # seconds

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/command_router.log"),
    ],
)
log = logging.getLogger("command_router")

# ── Command Map ─────────────────────────────────────────
# Maps !command prefixes to (script_name, min_args)
COMMANDS = {
    "!make-proposal":    ("make-proposal.sh",        2),  # email context
    "!send-proposal":    ("send-proposal.sh",        1),  # email
    "!busca-email":      ("enrich-email.sh",         3),  # first last domain
    "!busca-linkedin":   ("linkedin-sheets.sh",      1),  # tab [start] [end]
    "!admin":            ("admin-ops.sh",             0),  # [subcommand]
    "!generate-doc":     ("generate-doc.sh",          2),  # type content
    "!draft-email":      ("draft-email.sh",           2),  # company email [name] [priority] [context]
    "!calendar-status":  ("calendar-status.sh",       0),  # [query]
    "!calendar-create":  ("calendar-create-event.sh", 3),  # title datetime emails
    "!calendar-from-email": ("calendar-from-email.sh", 1), # query
    "!calendar-upload":  ("calendar-upload-ics.sh",   1),  # path
}

# ── Duplicate Prevention ────────────────────────────────
_processed_timestamps = set()
MAX_PROCESSED_CACHE = 1000


def _get_log_path():
    """Get today's gateway log file path."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"openclaw-{today}.log")


def _send_whatsapp(message):
    """Send a message back via openclaw CLI."""
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
        log.error("Failed to send WhatsApp message: %s", e)


def _parse_inbound_message(line):
    """
    Parse a gateway log line and extract inbound WhatsApp message data.

    Returns (sender, body, timestamp) or None if not an inbound message.
    """
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None

    # Match the specific log pattern: module=web-inbound, field "2"="inbound message"
    if data.get("2") != "inbound message":
        return None

    module_str = data.get("0", "")
    if "web-inbound" not in module_str:
        return None

    payload = data.get("1", {})
    if not isinstance(payload, dict):
        return None

    sender = payload.get("from", "")
    body = payload.get("body", "")
    timestamp = payload.get("timestamp", 0)

    if sender and body:
        return (sender, body, timestamp)

    return None


def _handle_help():
    """Return the help text for available commands."""
    lines = [
        "🤖 *OpenClaw Command Router — Comandos Disponibles*",
        "",
        "📋 *Propuestas:*",
        '• `!make-proposal <email> <contexto>` — Genera borrador AI',
        '• `!send-proposal <email>` — Envía el último borrador por email',
        "",
        "🔍 *Búsqueda:*",
        '• `!busca-email <nombre> <apellido> <dominio>` — Waterfall: Hunter→Snov→Scraping→SerpAPI→Permutaciones',
        '• `!busca-linkedin <tab> <start> <end>` — LinkedIn search → escribe URLs en Google Sheets',
        "",
        "📧 *Email:*",
        '• `!draft-email <company> <email> [name] [priority] [context]`',
        "",
        "🗓️ *Calendario:*",
        '• `!calendar-status [query]` — Estado invitaciones',
        '• `!calendar-create <título> <datetime> <emails>` — Crear evento + enviar ICS',
        '• `!calendar-from-email <query>` — Extrae ICS del email → Google Calendar',
        '• `!calendar-upload <path>` — Subir archivo ICS',
        "",
        "📄 *Documentos (con plantillas AI):*",
        '• `!generate-doc NDA "empresa: X, jurisdicción: Y"` — NDA profesional',
        '• `!generate-doc SOW "cliente: X, scope: Y, fee: Z"` — Statement of Work',
        '• `!generate-doc PROPUESTA "empresa: X, contexto: Y"` — Propuesta comercial',
        '• `!generate-doc <TIPO> <texto_libre>` — Documento genérico',
        "  _PDF + DOCX enviados por WhatsApp_",
        "",
        "⚙️ *Admin:*",
        '• `!admin status` — Docker + Gateway + APIs + PDFs',
        '• `!admin fix-all` — Reiniciar gateway + Docker (nuclear)',
        '• `!admin restart-gateway` — Solo gateway',
        '• `!admin restart-docker` — Solo contenedores Docker',
        '• `!admin restart-api` — Solo oc_api',
        "",
        "ℹ️ *Info:*",
        '• `!help` — Este menú',
        "",
        "💡 _Router local V6. Sin approvals. Sin cloud agent. 100% determinista._",
    ]
    return "\n".join(lines)


def _execute_command(body):
    """
    Parse the command from the message body and execute the corresponding script.
    """
    body_stripped = body.strip()

    # Handle !help separately (no script needed)
    if body_stripped == "!help":
        _send_whatsapp(_handle_help())
        return

    # Find matching command
    matched_cmd = None
    for cmd_prefix in sorted(COMMANDS.keys(), key=len, reverse=True):
        if body_stripped.startswith(cmd_prefix):
            matched_cmd = cmd_prefix
            break

    if not matched_cmd:
        log.warning("Unknown command: %s", body_stripped[:80])
        _send_whatsapp(f"❌ Comando desconocido: `{body_stripped[:50]}`\nEnvía `!help` para ver comandos.")
        return

    script_name, min_args = COMMANDS[matched_cmd]
    script_path = os.path.join(SKILLS_DIR, script_name)

    if not os.path.isfile(script_path):
        log.error("Script not found: %s", script_path)
        _send_whatsapp(f"❌ Script no encontrado: {script_name}")
        return

    # Extract arguments (everything after the command prefix)
    args_str = body_stripped[len(matched_cmd):].strip()

    # Split arguments respecting quotes
    if args_str:
        try:
            import shlex
            args = shlex.split(args_str)
        except ValueError:
            # If shlex fails (unmatched quotes), fall back to simple split
            args = args_str.split()
    else:
        args = []

    log.info("EXEC: %s %s (args: %s)", script_name, args, len(args))

    # Send acknowledgement
    _send_whatsapp(f"⚡ Ejecutando `{matched_cmd}` ...")

    # Execute the script
    cmd = ["bash", script_path] + args
    try:
        result = subprocess.run(
            cmd,
            timeout=SUBPROCESS_TIMEOUT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=WORK_DIR,
        )
        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace")[:500]
            log.error("Script %s failed (rc=%d): %s", script_name, result.returncode, stderr_text)
            # Don't send error via WA here — scripts send their own errors
        else:
            log.info("Script %s completed OK", script_name)

    except subprocess.TimeoutExpired:
        log.error("Script %s timed out after %ds", script_name, SUBPROCESS_TIMEOUT)
        _send_whatsapp(f"⏱️ Timeout: `{matched_cmd}` tardó más de {SUBPROCESS_TIMEOUT}s.")

    except Exception as e:
        log.error("Error executing %s: %s", script_name, e)
        _send_whatsapp(f"❌ Error ejecutando `{matched_cmd}`: {str(e)[:200]}")


def tail_log():
    """
    Main loop: tail the gateway log file and process incoming messages.
    Handles daily log rotation automatically.
    """
    log.info("=" * 60)
    log.info("Command Router started")
    log.info("Skills dir: %s", SKILLS_DIR)
    log.info("Allowed numbers: %s", ALLOWED_NUMBERS)
    log.info("Commands: %s", list(COMMANDS.keys()))
    log.info("=" * 60)

    current_log_path = None
    file_handle = None

    while True:
        try:
            new_log_path = _get_log_path()

            # Handle daily log rotation or initial start
            if new_log_path != current_log_path:
                if file_handle:
                    file_handle.close()
                    log.info("Log rotated: %s → %s", current_log_path, new_log_path)

                # Wait for the log file to exist
                while not os.path.exists(new_log_path):
                    log.info("Waiting for log file: %s", new_log_path)
                    time.sleep(5)

                file_handle = open(new_log_path, "r")
                # Seek to end (only process NEW messages)
                file_handle.seek(0, 2)
                current_log_path = new_log_path
                log.info("Tailing: %s", current_log_path)

            # Read new lines
            line = file_handle.readline()

            if not line:
                time.sleep(0.3)
                continue

            # Try to parse as inbound message
            parsed = _parse_inbound_message(line)
            if not parsed:
                continue

            sender, body, timestamp = parsed

            # Duplicate check
            msg_id = f"{timestamp}:{body[:50]}"
            if msg_id in _processed_timestamps:
                continue
            _processed_timestamps.add(msg_id)

            # Evict old entries to prevent memory leak
            if len(_processed_timestamps) > MAX_PROCESSED_CACHE:
                _processed_timestamps.clear()

            # Whitelist check
            if sender not in ALLOWED_NUMBERS:
                log.warning("BLOCKED sender: %s", sender)
                continue

            # Only process ! commands
            if not body.startswith("!"):
                continue

            log.info("CMD from %s: %s", sender[-4:], body[:100])
            _execute_command(body)

        except KeyboardInterrupt:
            log.info("Shutting down...")
            break
        except Exception as e:
            log.error("Unexpected error in main loop: %s", e)
            time.sleep(5)

    if file_handle:
        file_handle.close()


if __name__ == "__main__":
    tail_log()
