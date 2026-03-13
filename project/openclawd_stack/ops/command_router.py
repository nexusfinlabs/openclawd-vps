#!/usr/bin/env python3
"""
Command Router — Local VPS command executor for OpenClaw.

Tails the OpenClaw gateway log file, detects incoming WhatsApp AND Telegram
messages starting with '!', and executes the corresponding bash scripts.

Architecture:
  WhatsApp/Telegram → Gateway → log file → THIS ROUTER → scripts → openclaw message send

No HTTP server. No cloud agent. No approvals. 100% local.
"""

import json
import os
import re
import subprocess
import uuid
import sys
import time
import logging
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────
SKILLS_DIR = "/home/albi_agent/openclawd_stack/ops/openclaw_skills"
WORK_DIR = "/home/albi_agent/openclawd_stack"
LOG_DIR = "/tmp/openclaw"
ALLOWED_SENDERS = {"+34605693177", "7024795874"}  # WhatsApp + Telegram
SUBPROCESS_TIMEOUT = 120  # seconds
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
LINKEDIN_JOB_QUEUE = "oc:jobs:linkedin"
CONTEXT_KEY_PREFIX = "oc:context:"
CONTEXT_TTL = 7200  # 2 hours

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
    "!make-invoice":     ("make-invoice.sh",           1),  # "5000 consulting para TechCorp"
    "!send-invoice":     ("send-invoice.sh",           0),  # [invoice_ref] [email]
    "!make-ppt":         ("make-ppt.sh",               1),  # "5 slides sobre AI en fintech"
    "!analysis":         ("analysis.sh",                1),  # url [context]
}

# ── Duplicate Prevention ────────────────────────────────
_processed_timestamps = set()
MAX_PROCESSED_CACHE = 1000


def _get_log_path():
    """Get today's gateway log file path."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"openclaw-{today}.log")


def _send_reply(message, channel="whatsapp", target="34605693177"):
    """Send a message back via openclaw CLI on the given channel."""
    try:
        env = os.environ.copy()
        env["PATH"] = f"/home/albi_agent/.nvm/versions/node/v22.22.0/bin:{env.get('PATH', '')}"
        subprocess.run(
            [
                "openclaw", "message", "send",
                "--channel", channel,
                "--target", target,
                "--message", message,
            ],
            timeout=30,
            env=env,
            capture_output=True,
        )
    except Exception as e:
        log.error("Failed to send %s message: %s", channel, e)


def _parse_inbound_message(line):
    """
    Parse a gateway log line and extract inbound message data.
    Supports both WhatsApp and Telegram inbound formats.
    ONLY processes "web-inbound" / "telegram-inbound" lines.
    IGNORES "auto-reply", "outbound", "delivery" lines to prevent duplicates.

    Returns (sender, body, timestamp, channel) or None.
    """
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None

    # Skip non-inbound log lines (auto-reply, outbound, delivery, etc.)
    module_str = str(data.get("0", ""))
    if "auto-reply" in module_str or "outbound" in module_str or "delivery" in module_str:
        return None

    # --- WhatsApp inbound: module=web-inbound, field "2"="inbound message" ---
    if data.get("2") == "inbound message" and "web-inbound" in module_str:
        payload = data.get("1", {})
        if isinstance(payload, dict) and payload.get("body"):
            sender = payload.get("from", "")
            body = payload.get("body", "")
            timestamp = payload.get("timestamp", 0)
            if sender and body:
                return (sender, body, timestamp, "whatsapp")

    # --- Telegram inbound ---
    if "telegram" in module_str and "inbound" in module_str:
        payload = data.get("1", {})
        if isinstance(payload, dict) and payload.get("body"):
            sender = str(payload.get("from", ""))
            body = payload.get("body", "")
            timestamp = payload.get("timestamp", 0)
            if sender and body:
                return (sender, body, timestamp, "telegram")

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
        "🧾 *Facturas:*",
        '• `!make-invoice 5000 consulting para TechCorp` — Genera factura PDF',
        '• `!send-invoice OC-FRA003` — Envía la factura por email',
        '• `!send-invoice OC-FRA003 email@client.com` — Envía + actualiza email',
        "  _Numeración automática. DB de clientes. IVA 21% + IRPF 15%_",
        "",
        "📊 *Presentaciones:*",
        '• `!make-ppt 5 slides sobre AI en fintech` — PPTX profesional (PptxGenJS)',
        '• `!make-ppt --html 5 slides sobre AI` — HTML Reveal.js (animaciones)',
        '• `!make-ppt --palette dark-premium 5 slides` — Paleta específica',
        '• `!make-ppt --context 5 slides` — Usa contexto guardado',
        "  _Paletas: navy-executive, dark-premium, clean-bold, midnight, teal-trust_",
        "",
        "🔍 *Análisis Web:*",
        '• `!analysis https://example.com` — Scraping + análisis LLM profundo',
        '• `!analysis https://example.com contexto extra` — Con contexto',
        '• `!analysis --context https://example.com` — Usa !context guardado',
        "  _Sigue links, lee PDFs/HTML, genera reporte .md_",
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
        "📝 *Contexto (persistente):*",
        '• `!context norgine <texto>` — Guarda como norgine.md',
        '• `!context <texto>` — Guarda como default.md',
        '• `!context-list` — Ver todos los contextos guardados',
        '• `!context-show norgine` — Ver contenido',
        '• `!context-clear norgine` — Borrar uno',
        "  _Luego: `!make-ppt --context norgine --template 5 10 slides`_",
        "",
        "💡 _Router local V8. Sin approvals. Sin cloud agent. 100% determinista._",
    ]
    return "\n".join(lines)


def _enqueue_linkedin_job(args, channel="whatsapp", target="34605693177"):
    """
    Enqueue a LinkedIn search job in Redis for async processing by linkedin_worker.py.
    Returns immediately — no 120s timeout risk.
    """
    import redis as _redis

    tab = args[0] if len(args) >= 1 else "payments"
    start_row = int(args[1]) if len(args) >= 2 else 2
    end_row = int(args[2]) if len(args) >= 3 else None

    job_id = str(uuid.uuid4())[:8]
    job = {
        "job_id": job_id,
        "tab": tab,
        "start_row": start_row,
        "end_row": end_row,
        "channel": channel,
        "target": target,
    }

    try:
        r = _redis.from_url(REDIS_URL, decode_responses=True)
        r.rpush(LINKEDIN_JOB_QUEUE, json.dumps(job))
        queue_len = r.llen(LINKEDIN_JOB_QUEUE)
        log.info("LinkedIn job enqueued: %s (queue len=%d)", job, queue_len)

        rows_desc = f"{start_row}-{end_row}" if end_row else f"{start_row}+"
        _send_reply(
            f"🔍 LinkedIn search encolado\n"
            f"• Job: `{job_id}`\n"
            f"• Tab: `{tab}` | Rows: `{rows_desc}`\n"
            f"• Cola: {queue_len} job(s) pendientes\n\n"
            f"El worker lo procesará en background (hasta 10 min). "
            f"Recibirás notificación cuando termine.",
            channel=channel, target=target,
        )
    except Exception as e:
        log.error("Failed to enqueue LinkedIn job: %s", e)
        _send_reply(f"❌ Error encolando LinkedIn job: {str(e)[:200]}", channel=channel, target=target)


CONTEXT_DIR = "/home/albi_agent/.openclaw/workspace/context"


def _handle_context(body_stripped, channel="whatsapp", target="34605693177"):
    """
    Handle !context, !context-show, !context-list, !context-clear commands.
    Stores text as named .md files in CONTEXT_DIR for persistent reuse.

    Usage:
      !context norgine <long text>       → saves context/norgine.md
      !context <long text>               → saves context/default.md
      !context-list                      → lists all saved contexts
      !context-show norgine              → shows norgine.md content
      !context-clear norgine             → deletes norgine.md
      !context-clear                     → deletes all
    """
    import re as _re
    os.makedirs(CONTEXT_DIR, exist_ok=True)

    try:
        # !context-clear [name]
        if body_stripped.startswith("!context-clear"):
            name = body_stripped[len("!context-clear"):].strip()
            if name:
                path = os.path.join(CONTEXT_DIR, f"{name.replace('.md','')}.md")
                if os.path.exists(path):
                    os.unlink(path)
                    _send_reply(f"🗑️ Contexto `{name}` borrado.", channel=channel, target=target)
                else:
                    _send_reply(f"❌ No existe contexto `{name}`.", channel=channel, target=target)
            else:
                # Clear all
                count = 0
                for f in os.listdir(CONTEXT_DIR):
                    if f.endswith(".md"):
                        os.unlink(os.path.join(CONTEXT_DIR, f))
                        count += 1
                _send_reply(f"🗑️ {count} contexto(s) borrados.", channel=channel, target=target)
            return

        # !context-list
        if body_stripped == "!context-list":
            files = sorted(f for f in os.listdir(CONTEXT_DIR) if f.endswith(".md"))
            if files:
                listing = "\n".join(
                    f"• `{f}` ({os.path.getsize(os.path.join(CONTEXT_DIR, f)):,} chars)"
                    for f in files
                )
                _send_reply(f"📂 *Contextos guardados:*\n{listing}", channel=channel, target=target)
            else:
                _send_reply("📂 No hay contextos guardados.", channel=channel, target=target)
            return

        # !context-show [name]
        if body_stripped.startswith("!context-show"):
            name = body_stripped[len("!context-show"):].strip() or "default"
            path = os.path.join(CONTEXT_DIR, f"{name.replace('.md','')}.md")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    ctx = f.read()
                preview = ctx[:500] + ("..." if len(ctx) > 500 else "")
                _send_reply(
                    f"📝 *Contexto `{name}`* ({len(ctx):,} chars):\n\n{preview}",
                    channel=channel, target=target,
                )
            else:
                _send_reply(f"📝 No existe contexto `{name}`.", channel=channel, target=target)
            return

        # !context [name] <text> — store
        text = body_stripped[len("!context"):].strip()
        if not text:
            _send_reply(
                "❌ Uso:\n"
                "`!context norgine <texto largo>` → guarda como norgine.md\n"
                "`!context <texto>` → guarda como default.md\n"
                "`!context-list` → ver todos\n"
                "`!context-show norgine` → ver contenido\n"
                "`!context-clear norgine` → borrar\n\n"
                "Luego: `!make-ppt --context norgine --template 5 10 slides`",
                channel=channel, target=target,
            )
            return

        # Parse: first word = name (if alphanumeric), rest = content
        # If first word looks like content (has spaces in it, or is very long), use "default"
        parts = text.split(None, 1)
        if len(parts) >= 2 and _re.match(r'^[a-zA-Z0-9_\-]+$', parts[0]) and len(parts[0]) <= 40:
            ctx_name = parts[0].lower()
            ctx_text = parts[1]
        else:
            ctx_name = "default"
            ctx_text = text

        filename = f"{ctx_name}.md"
        filepath = os.path.join(CONTEXT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(ctx_text)

        preview = ctx_text[:200] + ("..." if len(ctx_text) > 200 else "")
        _send_reply(
            f"✅ Contexto guardado: `{filename}` ({len(ctx_text):,} chars)\n\n"
            f"_{preview}_\n\n"
            f"Ahora puedes usar:\n"
            f"• `!make-ppt --context {ctx_name} --template 5 10 slides`\n"
            f"• `!analysis --context {ctx_name} https://url`\n"
            f"• `!context-list` para ver todos\n"
            f"• `!context-show {ctx_name}` para verificar",
            channel=channel, target=target,
        )
    except Exception as e:
        log.error("Context command error: %s", e)
        _send_reply(f"❌ Error con contexto: {str(e)[:200]}", channel=channel, target=target)


def _execute_command(body, channel="whatsapp", target="34605693177"):
    """
    Parse the command from the message body and execute the corresponding script.
    Replies on the same channel the message came from.
    """
    body_stripped = body.strip()

    # Handle !help separately (no script needed)
    if body_stripped == "!help":
        _send_reply(_handle_help(), channel=channel, target=target)
        return

    # Handle !context commands (no script needed — direct Redis)
    if body_stripped.startswith("!context"):
        _handle_context(body_stripped, channel=channel, target=target)
        return

    # Find matching command
    matched_cmd = None
    for cmd_prefix in sorted(COMMANDS.keys(), key=len, reverse=True):
        if body_stripped.startswith(cmd_prefix):
            matched_cmd = cmd_prefix
            break

    if not matched_cmd:
        log.warning("Unknown command: %s", body_stripped[:80])
        _send_reply(f"❌ Comando desconocido: `{body_stripped[:50]}`\nEnvía `!help` para ver comandos.", channel=channel, target=target)
        return

    script_name, min_args = COMMANDS[matched_cmd]

    # Extract arguments (everything after the command prefix)
    args_str = body_stripped[len(matched_cmd):].strip()
    if args_str:
        try:
            import shlex
            args = shlex.split(args_str)
        except ValueError:
            args = args_str.split()
    else:
        args = []

    # ── ASYNC PATH: LinkedIn search → Redis queue (no 120s timeout) ──
    if matched_cmd == "!busca-linkedin":
        log.info("ASYNC: LinkedIn job → Redis queue (args: %s)", args)
        _enqueue_linkedin_job(args, channel=channel, target=target)
        return

    # ── SYNC PATH: all other commands ────────────────────────────────
    script_path = os.path.join(SKILLS_DIR, script_name)

    if not os.path.isfile(script_path):
        log.error("Script not found: %s", script_path)
        _send_reply(f"❌ Script no encontrado: {script_name}", channel=channel, target=target)
        return

    log.info("EXEC: %s %s (args: %s)", script_name, args, len(args))

    # Send acknowledgement
    _send_reply(f"⚡ Ejecutando `{matched_cmd}` ...", channel=channel, target=target)

    # Execute the script with sender context
    env = os.environ.copy()
    env["SENDER_TARGET"] = target
    env["SENDER_CHANNEL"] = channel
    cmd = ["bash", script_path] + args
    try:
        result = subprocess.run(
            cmd,
            timeout=SUBPROCESS_TIMEOUT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=WORK_DIR,
            env=env,
        )
        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace")[:500]
            log.error("Script %s failed (rc=%d): %s", script_name, result.returncode, stderr_text)
        else:
            log.info("Script %s completed OK", script_name)

    except subprocess.TimeoutExpired:
        log.error("Script %s timed out after %ds", script_name, SUBPROCESS_TIMEOUT)
        _send_reply(f"⏱️ Timeout: `{matched_cmd}` tardó más de {SUBPROCESS_TIMEOUT}s.", channel=channel, target=target)

    except Exception as e:
        log.error("Error executing %s: %s", script_name, e)
        _send_reply(f"❌ Error ejecutando `{matched_cmd}`: {str(e)[:200]}", channel=channel, target=target)


def tail_log():
    """
    Main loop: tail the gateway log file and process incoming messages.
    Handles daily log rotation automatically.
    """
    log.info("=" * 60)
    log.info("Command Router started")
    log.info("Skills dir: %s", SKILLS_DIR)
    log.info("Allowed senders: %s", ALLOWED_SENDERS)
    log.info("Commands: %s", list(COMMANDS.keys()))
    log.info("Channels: WhatsApp + Telegram (unified)")
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

            sender, body, timestamp, channel = parsed

            # Duplicate check
            msg_id = f"{timestamp}:{body[:50]}"
            if msg_id in _processed_timestamps:
                continue
            _processed_timestamps.add(msg_id)

            # Evict old entries to prevent memory leak
            if len(_processed_timestamps) > MAX_PROCESSED_CACHE:
                _processed_timestamps.clear()

            # Whitelist check — normalize sender for matching
            sender_clean = sender.replace("@s.whatsapp.net", "").lstrip("+")
            sender_match = any(
                s.lstrip("+") == sender_clean or s == sender
                for s in ALLOWED_SENDERS
            )
            if not sender_match:
                log.warning("BLOCKED sender: %s (channel: %s)", sender, channel)
                continue

            # Only process ! commands
            if not body.startswith("!"):
                continue

            # Determine reply target based on channel
            target = sender_clean
            if channel == "whatsapp":
                target = sender_clean.replace("@s.whatsapp.net", "")

            log.info("CMD [%s] from %s: %s", channel, sender[-8:], body[:100])
            _execute_command(body, channel=channel, target=target)

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
