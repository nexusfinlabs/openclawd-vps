from fastapi import FastAPI
from pydantic import BaseModel
import os
import json
import redis
from sqlalchemy import text

from db import engine, SessionLocal, Base
import models  # registra modelos

app = FastAPI(title="OpenClawd Stack API", version="0.2")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

class JobRequest(BaseModel):
    url: str
    note: str | None = None

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    redis_ok = False
    try:
        r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {"ok": True, "redis": redis_ok, "db": db_ok}

@app.post("/jobs")
def create_job(req: JobRequest):
    job_id = r.incr("jobs:seq")
    payload = {"id": int(job_id), "url": req.url, "note": req.note or ""}
    r.rpush("jobs:queue", json.dumps(payload))
    return {"job_id": int(job_id), "queued": True}

@app.get("/pages")
def list_pages(limit: int = 50):
    with SessionLocal() as db:
        rows = db.query(models.Page).order_by(models.Page.id.desc()).limit(limit).all()
        return [
            {
                "id": p.id,
                "url": p.url,
                "title": p.title,
                "meta_description": p.meta_description,
                "emails": p.emails,
                "phones": p.phones,
                "fetched_at": str(p.fetched_at),
            }
            for p in rows
        ]
