"""
oc_exporter – Incremental Postgres → Google Sheets exporter.
Endpoints:
  GET  /health         – DB + Sheets connectivity
  GET  /status         – checkpoint positions
  POST /export/pages   – export pages to 'companies' tab
  POST /export/events  – log an event to 'events' tab
"""

import os
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, Query
from sqlalchemy import text, func

from db import engine, SessionLocal, Base
from models import Page, ExportCheckpoint
from sheets import append_rows, sheet_health_check
from auth import require_token

app = FastAPI(title="OpenClawd Exporter", version="0.1")

SHEETS_TAB_COMPANIES = os.getenv("SHEETS_TAB_COMPANIES", "companies")
SHEETS_TAB_EVENTS = os.getenv("SHEETS_TAB_EVENTS", "events")


# ── Startup ─────────────────────────────────────────────
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


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

    sheets_ok = sheet_health_check()

    return {"ok": db_ok and sheets_ok, "db": db_ok, "sheets": sheets_ok}


# ── GET /status ─────────────────────────────────────────
@app.get("/status")
def status():
    with SessionLocal() as db:
        total_pages = db.query(func.count(Page.id)).scalar() or 0
        max_page_id = db.query(func.max(Page.id)).scalar() or 0

        checkpoints = db.query(ExportCheckpoint).all()
        cp_data = {
            cp.name: {"last_id": cp.last_id, "updated_at": str(cp.updated_at)}
            for cp in checkpoints
        }

    return {
        "total_pages": total_pages,
        "max_page_id": max_page_id,
        "checkpoints": cp_data,
    }


# ── POST /export/pages ──────────────────────────────────
@app.post("/export/pages")
def export_pages(
    limit: int = Query(default=200, ge=1, le=1000),
    _token: None = Depends(require_token),
):
    """Export pages incrementally to the 'companies' tab."""
    cp_name = "pages"

    with SessionLocal() as db:
        # Get or create checkpoint
        cp = db.query(ExportCheckpoint).filter_by(name=cp_name).first()
        if not cp:
            cp = ExportCheckpoint(name=cp_name, last_id=0)
            db.add(cp)
            db.commit()
            db.refresh(cp)

        last_id = cp.last_id

        # Fetch new pages since checkpoint
        pages = (
            db.query(Page)
            .filter(Page.id > last_id)
            .order_by(Page.id.asc())
            .limit(limit)
            .all()
        )

        if not pages:
            return {
                "exported": 0,
                "checkpoint": last_id,
                "message": "No new pages to export",
            }

        # Build rows for Sheets: [id, url, title, meta_description, emails, phones, fetched_at]
        rows = []
        for p in pages:
            rows.append([
                p.id,
                p.url or "",
                p.title or "",
                p.meta_description or "",
                p.emails or "",
                p.phones or "",
                str(p.fetched_at) if p.fetched_at else "",
            ])

        # Write to Google Sheets
        append_rows(SHEETS_TAB_COMPANIES, rows)

        # Update checkpoint
        new_last_id = pages[-1].id
        cp.last_id = new_last_id
        cp.updated_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "exported": len(rows),
        "checkpoint_from": last_id,
        "checkpoint_to": new_last_id,
        "tab": SHEETS_TAB_COMPANIES,
    }


# ── POST /export/events ─────────────────────────────────
@app.post("/export/events")
def export_events(
    _token: None = Depends(require_token),
):
    """Log a timestamped export event to the 'events' tab."""
    now = datetime.now(timezone.utc).isoformat()

    with SessionLocal() as db:
        total_pages = db.query(func.count(Page.id)).scalar() or 0

        cp = db.query(ExportCheckpoint).filter_by(name="pages").first()
        last_exported_id = cp.last_id if cp else 0

    row = [now, "export_snapshot", str(total_pages), str(last_exported_id)]
    append_rows(SHEETS_TAB_EVENTS, [row])

    return {
        "logged": True,
        "tab": SHEETS_TAB_EVENTS,
        "event": {
            "timestamp": now,
            "total_pages": total_pages,
            "last_exported_id": last_exported_id,
        },
    }
