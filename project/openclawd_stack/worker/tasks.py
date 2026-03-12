import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "oc_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

@celery_app.task(name="oc.ping")
def ping():
    return {"ok": True}

# En Fase 2: oc.browse(url) usando Playwright, extraer data, guardar en Postgres.
