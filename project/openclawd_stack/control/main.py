"""
oc_control – WhatsApp Agent Control Microservice.

Receives messages forwarded by OpenClaw WhatsApp channel.
Whitelist-only access. Logs every interaction to Postgres + Google Sheets.

Security:
  - Whitelist enforced (ALLOWED_NUMBERS)
  - No subprocess, no shell — only httpx to internal APIs
  - Command whitelist — no free-text execution
  - Rate limiting: 10 commands/min per sender

Endpoints:
  GET  /health      – DB connectivity check
  POST /whatsapp    – Main webhook (whitelist enforced)
"""

import os
import time
import logging
import asyncio
from datetime import datetime, timezone
from collections import defaultdict

import httpx
from fastapi import FastAPI, Request
from sqlalchemy import text, func

from db import engine, SessionLocal, Base
from models import ControlLog, Page, ExportCheckpoint
from sheets import log_event_to_sheets

# ── Config ──────────────────────────────────────────────
ALLOWED_NUMBERS = [
    n.strip()
    for n in os.getenv("ALLOWED_NUMBERS", "34663103334").split(",")
    if n.strip()
]

OC_API_URL = os.getenv("OC_API_URL", "http://oc_api:8000")
OC_EXPORTER_URL = os.getenv("OC_EXPORTER_URL", "http://oc_exporter:8001")
EXPORTER_TOKEN = os.getenv("EXPORTER_TOKEN", "")

# Rate limiting: max commands per window
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

# Command timeout (seconds)
CMD_TIMEOUT = float(os.getenv("CMD_TIMEOUT", "15"))

# Response max length for WhatsApp (chars)
MAX_RESPONSE_LEN = 1500

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("oc_control")

app = FastAPI(title="OpenClawd Control", version="0.2")

# In-memory rate limiter: {sender: [timestamp, ...]}
_rate_store: dict[str, list[float]] = defaultdict(list)


# ── Startup ─────────────────────────────────────────────
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    log.info("oc_control v0.2 started — allowed: %s, rate: %d/%ds",
             ALLOWED_NUMBERS, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW)


# ── Rate Limiter ────────────────────────────────────────
def _check_rate_limit(sender: str) -> bool:
    """Returns True if sender is within rate limit, False if exceeded."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Prune old entries
    _rate_store[sender] = [t for t in _rate_store[sender] if t > window_start]

    if len(_rate_store[sender]) >= RATE_LIMIT_MAX:
        return False

    _rate_store[sender].append(now)
    return True


# ── Helpers ─────────────────────────────────────────────
def _log_interaction(sender: str, command: str, response: str, status: str):
    """Persist interaction to Postgres control_logs."""
    try:
        with SessionLocal() as db:
            entry = ControlLog(
                sender=sender,
                command=command,
                response=response[:2000],  # cap at ~2KB
                status=status,
            )
            db.add(entry)
            db.commit()
    except Exception as e:
        log.error("Failed to log interaction to DB: %s", e)

    # Also log to Google Sheets events tab (fire-and-forget)
    try:
        now = datetime.now(timezone.utc).isoformat()
        log_event_to_sheets([now, "whatsapp_cmd", command, status, response[:200]])
    except Exception as e:
        log.error("Failed to log to Sheets: %s", e)


def _fmt(title: str, body: str, tip: str = "") -> str:
    """Format a professional response block, capped for WhatsApp."""
    lines = [f"🤖 *{title}*", "", body]
    if tip:
        lines += ["", f"💡 _{tip}_"]
    result = "\n".join(lines)
    # Cap response length for WhatsApp readability
    if len(result) > MAX_RESPONSE_LEN:
        result = result[:MAX_RESPONSE_LEN - 20] + "\n\n[...recortado]"
    return result


def _diagnose_error(error: Exception, context: str) -> str:
    """Auto-diagnose an error and suggest fixes."""
    err_str = str(error).lower()
    diagnosis = f"⚠️ Error en *{context}*: `{str(error)[:150]}`\n\n"

    if "connection refused" in err_str or "connect" in err_str:
        diagnosis += (
            "🔍 *Diagnóstico*: El servicio no acepta conexiones.\n"
            "🛠 *Acción sugerida*:\n"
            "1. Verificar que el contenedor esté corriendo: `docker ps`\n"
            "2. Reiniciar: `docker compose restart <service>`\n"
            "3. Revisar logs: `docker logs <container>`"
        )
    elif "timeout" in err_str:
        diagnosis += (
            "🔍 *Diagnóstico*: El servicio tarda demasiado en responder.\n"
            "🛠 *Acción sugerida*:\n"
            "1. Revisar carga CPU/RAM del VPS: `htop`\n"
            "2. Postgres podría estar bloqueado: revisar conexiones activas\n"
            "3. Si persiste, reiniciar el stack: `docker compose restart`"
        )
    elif "database" in err_str or "psycopg" in err_str or "sqlalchemy" in err_str:
        diagnosis += (
            "🔍 *Diagnóstico*: Problema de base de datos.\n"
            "🛠 *Acción sugerida*:\n"
            "1. Verificar Postgres: `docker exec oc_postgres pg_isready`\n"
            "2. Revisar disco: `df -h` (Postgres necesita espacio)\n"
            "3. Revisar conexiones: `docker logs oc_postgres --tail 20`"
        )
    elif "permission" in err_str or "auth" in err_str:
        diagnosis += (
            "🔍 *Diagnóstico*: Problema de permisos o autenticación.\n"
            "🛠 *Acción sugerida*:\n"
            "1. Verificar EXPORTER_TOKEN en .env\n"
            "2. Confirmar credenciales de Google Sheets\n"
            "3. Revisar permisos del service account"
        )
    else:
        diagnosis += (
            "🔍 *Diagnóstico*: Error no categorizado.\n"
            "🛠 *Acción sugerida*:\n"
            "1. Revisar logs: `docker logs oc_control --tail 50`\n"
            "2. Reiniciar servicio: `docker compose restart control`\n"
            "3. Si persiste, envía 'health' para una vista general"
        )

    return diagnosis


# ── Command Handlers ────────────────────────────────────
async def _cmd_help() -> str:
    return _fmt(
        "OpenClawd Control Panel",
        (
            "📋 *Comandos:*\n"
            "• `status` — Servicios\n"
            "• `pages` — Stats crawling\n"
            "• `health` — Health check\n"
            "• `export` — Exportar a Sheets\n"
            "• `scrape <url>` — Encolar URL\n"
            "• `logs` — Últimas 5 acciones\n"
            "• `help` — Este menú"
        ),
        "Solo tu número tiene acceso. 24/7.",
    )


async def _cmd_status() -> str:
    """Check health of internal services via their /health endpoints."""
    services = {
        "oc_api": f"{OC_API_URL}/health",
        "oc_exporter": f"{OC_EXPORTER_URL}/health",
    }
    lines = []
    all_ok = True

    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in services.items():
            try:
                r = await client.get(url)
                data = r.json()
                ok = data.get("ok", False)
                icon = "🟢" if ok else "🔴"
                lines.append(f"{icon} *{name}* — {'OK' if ok else 'FAIL'}")
                if not ok:
                    all_ok = False
                    for k, v in data.items():
                        if k != "ok" and not v:
                            lines.append(f"   ⚠️ {k}: down")
            except httpx.ConnectError:
                lines.append(f"🔴 *{name}* — no responde")
                all_ok = False
            except Exception as e:
                lines.append(f"🟡 *{name}* — {str(e)[:80]}")
                all_ok = False

    # Postgres direct check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        lines.append("🟢 *postgres* — OK")
    except Exception:
        lines.append("🔴 *postgres* — no responde")
        all_ok = False

    summary = "✅ OK" if all_ok else "⚠️ Problemas"
    tip = "" if all_ok else "ssh openclawd-vps 'sudo docker logs <container>'"
    return _fmt(f"Sistema — {summary}", "\n".join(lines), tip)


async def _cmd_pages() -> str:
    """Get page statistics from the database."""
    try:
        with SessionLocal() as db:
            total = db.query(func.count(Page.id)).scalar() or 0
            max_id = db.query(func.max(Page.id)).scalar() or 0
            with_emails = db.query(func.count(Page.id)).filter(
                Page.emails.isnot(None), Page.emails != ""
            ).scalar() or 0

            cp = db.query(ExportCheckpoint).filter_by(name="pages").first()
            exported_id = cp.last_id if cp else 0
            pending = max_id - exported_id

        lines = [
            f"📊 Total: *{total}*",
            f"📧 Con emails: *{with_emails}*",
            f"📤 Exportadas: *{exported_id}*",
            f"⏳ Pendientes: *{pending}*",
        ]

        tip = ""
        if pending > 50:
            tip = f"{pending} pendientes → envía 'export'"
        elif pending > 0:
            tip = "Pocas pendientes. 'export' cuando quieras."
        else:
            tip = "Todo sincronizado 👌"

        return _fmt("Crawling Stats", "\n".join(lines), tip)
    except Exception as e:
        return _fmt("Error", _diagnose_error(e, "pages query"))


async def _cmd_health() -> str:
    """Detailed health check of all services."""
    checks = {}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["Postgres"] = True
    except Exception:
        checks["Postgres"] = False

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{OC_API_URL}/health")
            checks["API"] = r.json().get("ok", False)
        except Exception:
            checks["API"] = False

        try:
            r = await client.get(f"{OC_EXPORTER_URL}/health")
            data = r.json()
            checks["Exporter"] = data.get("ok", False)
            checks["Sheets"] = data.get("sheets", False)
        except Exception:
            checks["Exporter"] = False

    lines = [f"{'✅' if v else '❌'} {k}" for k, v in checks.items()]
    all_ok = all(checks.values())

    return _fmt(
        "Health Check",
        "\n".join(lines),
        "100% operativo ✅" if all_ok else "Revisa servicios con ❌",
    )


async def _cmd_export() -> str:
    """Trigger incremental export to Google Sheets."""
    if not EXPORTER_TOKEN:
        return _fmt("Error", "EXPORTER_TOKEN no configurado.")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.post(
                f"{OC_EXPORTER_URL}/export/pages?limit=200",
                headers={"Authorization": f"Bearer {EXPORTER_TOKEN}"},
            )
            data = r.json()
            exported = data.get("exported", 0)

            if exported == 0:
                return _fmt("Export", "📭 Sin páginas nuevas.", "Sheets al día.")

            return _fmt(
                "Export ✅",
                (
                    f"📤 Exportadas: *{exported}*\n"
                    f"📍 {data.get('checkpoint_from','?')} → {data.get('checkpoint_to','?')}"
                ),
                "Datos en Sheets.",
            )
        except Exception as e:
            return _fmt("Error", _diagnose_error(e, "export"))


async def _cmd_scrape(url: str) -> str:
    """Queue a URL for scraping via oc_api."""
    if not url.startswith(("http://", "https://")):
        return _fmt("Error", f"URL inválida: `{url[:100]}`\nUsa http:// o https://")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(
                f"{OC_API_URL}/jobs",
                json={"url": url, "note": "via WhatsApp control"},
            )
            if r.status_code == 200:
                return _fmt(
                    "Scrape ✅",
                    f"🔗 {url}\n📋 En cola para el worker.",
                    "Envía 'pages' en unos minutos.",
                )
            else:
                return _fmt("Error", f"API status {r.status_code}: {r.text[:150]}")
        except Exception as e:
            return _fmt("Error", _diagnose_error(e, "scrape"))


async def _cmd_logs() -> str:
    """Show last 5 interactions from control_logs."""
    try:
        with SessionLocal() as db:
            entries = (
                db.query(ControlLog)
                .order_by(ControlLog.id.desc())
                .limit(5)
                .all()
            )
            if not entries:
                return _fmt("Logs", "Sin interacciones aún.")

            lines = []
            for e in reversed(entries):
                ts = e.created_at.strftime("%H:%M") if e.created_at else "?"
                icon = "✅" if e.status == "ok" else "❌"
                lines.append(f"{icon} {ts} — `{e.command}`")

            return _fmt("Últimas 5", "\n".join(lines))
    except Exception as e:
        return _fmt("Error", _diagnose_error(e, "logs query"))


# ── Command Router ──────────────────────────────────────
COMMANDS = {
    "help": _cmd_help,
    "status": _cmd_status,
    "pages": _cmd_pages,
    "health": _cmd_health,
    "export": _cmd_export,
    "logs": _cmd_logs,
}


# ── GET /health ─────────────────────────────────────────
@app.get("/health")
def health():
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {"ok": db_ok, "db": db_ok, "service": "oc_control"}


# ── POST /whatsapp ──────────────────────────────────────
@app.post("/whatsapp")
async def whatsapp_hook(request: Request):
    """
    Main webhook for WhatsApp messages forwarded by OpenClaw.

    Expected payload:
    {"from": "34663103334", "message": "status"}
    """
    data = await request.json()

    sender = data.get("from", "").replace("+", "").replace(" ", "").replace("-", "")
    message = data.get("message", "").strip().lower()

    # ── Whitelist check (silent reject) ─────────────────
    if sender not in ALLOWED_NUMBERS:
        log.warning("BLOCKED: %s", sender)
        return {"status": "ignored"}

    if not message:
        return {"reply": _fmt("Error", "Mensaje vacío. Envía `help`.")}

    # ── Rate limit check ────────────────────────────────
    if not _check_rate_limit(sender):
        log.warning("RATE LIMITED: %s", sender)
        return {"reply": _fmt("⏳ Rate Limit", f"Máximo {RATE_LIMIT_MAX} comandos/{RATE_LIMIT_WINDOW}s.\nEspera unos segundos.")}

    log.info("CMD %s: %s", sender[-4:], message)

    # ── Route command with timeout ──────────────────────
    status = "ok"
    try:
        if message in COMMANDS:
            reply = await asyncio.wait_for(COMMANDS[message](), timeout=CMD_TIMEOUT)
        elif message.startswith("scrape "):
            url = message.split(" ", 1)[1].strip()
            reply = await asyncio.wait_for(_cmd_scrape(url), timeout=CMD_TIMEOUT)
        else:
            reply = _fmt(
                "Comando no reconocido",
                f"`{message[:80]}`",
                "Envía `help` para comandos.",
            )
            status = "fail"
    except asyncio.TimeoutError:
        reply = _fmt(
            "⏱ Timeout",
            f"El comando `{message[:50]}` tardó más de {CMD_TIMEOUT}s.",
            "El servicio puede estar saturado. Intenta 'health' para diagnosticar.",
        )
        status = "timeout"
    except Exception as e:
        reply = _fmt("Error Inesperado", _diagnose_error(e, message))
        status = "fail"

    # ── Log interaction (Postgres + Sheets) ─────────────
    _log_interaction(sender, message, reply, status)

    return {"reply": reply}
