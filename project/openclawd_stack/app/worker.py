import os
import time
import json
import random

import redis
from sqlalchemy.orm import Session

from db import SessionLocal
import models
from scrape import scrape_requests

# Force requests to use certifi CA bundle (more reliable inside containers)
try:
    import certifi
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE = os.getenv("JOBS_QUEUE", "jobs:queue")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

NO_RETRY_MARKERS = (
    "NameResolutionError",
    "Failed to resolve",
    "Temporary failure in name resolution",
    "CERTIFICATE_VERIFY_FAILED",
    "SSLV3_ALERT_HANDSHAKE_FAILURE",
    "handshake failure",
)

def save_page(db: Session, data: dict):
    p = models.Page(
        url=data.get("url"),
        title=data.get("title"),
        meta_description=data.get("meta_description"),
        emails=data.get("emails"),
        phones=data.get("phones"),
        forms=data.get("forms"),
    )
    db.add(p)
    db.commit()

def connect_redis():
    return redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=10,
        health_check_interval=30,
    )

def parse_payload(payload: str) -> dict:
    payload = (payload or "").strip()
    if not payload:
        return {"url": ""}

    if payload.startswith("{") and payload.endswith("}"):
        try:
            return json.loads(payload)
        except Exception:
            try:
                return json.loads(payload.replace("'", '"'))
            except Exception:
                return {"url": payload}

    return {"url": payload}

def should_retry(err: Exception) -> bool:
    msg = f"{type(err).__name__}: {err}"
    return not any(m in msg for m in NO_RETRY_MARKERS)

def requeue(rds: redis.Redis, job: dict):
    attempts = int(job.get("attempts", 0))
    job["attempts"] = attempts + 1
    rds.rpush(QUEUE, json.dumps(job))

def run():
    rds = None
    backoff = 1.0

    print("worker: started, waiting for jobs...")
    while True:
        # Ensure redis connection
        if rds is None:
            try:
                rds = connect_redis()
                rds.ping()
                backoff = 1.0
            except Exception as e:
                print(f"worker: redis connect failed: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 1.7, 30.0)
                continue

        # Wait for job
        try:
            item = rds.blpop(QUEUE, timeout=5)
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            print(f"worker: redis blpop error (reconnect): {e}")
            rds = None
            continue

        if not item:
            continue

        _, payload = item
        job = parse_payload(payload)
        url = (job.get("url") or "").strip()
        attempts = int(job.get("attempts", 0))

        if not url:
            print("worker: got empty url payload, skipping")
            continue

        print(f"worker: job url={url} attempts={attempts}")

        try:
            data = scrape_requests(url)
            with SessionLocal() as db:
                save_page(db, data)
            print("worker: saved")
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            retryable = should_retry(e)

            if retryable and attempts < MAX_RETRIES:
                sleep_s = 1.0 + random.random() * 2.0
                print(f"worker: failed (retryable): {msg} -> requeue after {sleep_s:.1f}s")
                time.sleep(sleep_s)
                try:
                    requeue(rds, job)
                except Exception as re:
                    print(f"worker: requeue failed (reconnect): {re}")
                    rds = None
            else:
                print(f"worker: failed (no-retry): {msg}")

if __name__ == "__main__":
    run()
