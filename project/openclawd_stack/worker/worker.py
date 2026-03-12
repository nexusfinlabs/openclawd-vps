import os
import json
import re
import time
import requests
from bs4 import BeautifulSoup
import psycopg

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL")

# REDIS_URL es redis://redis:6379/0
import redis
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}")

def extract(s: str):
    emails = sorted(set(EMAIL_RE.findall(s or "")))[:20]
    phones = sorted(set(m.group(0) for m in PHONE_RE.finditer(s or "")))[:20]
    return ",".join(emails), ",".join(phones)

def scrape_url(url: str):
    resp = requests.get(url, timeout=25, headers={"User-Agent":"Mozilla/5.0 (compatible; OpenClawdWorker/0.2)"})
    resp.raise_for_status()
    html = resp.text

    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")[:300]

    meta_desc = ""
    md = soup.find("meta", attrs={"name": "description"})
    if md and md.get("content"):
        meta_desc = md["content"].strip()[:500]

    emails, phones = extract(html)
    return title, meta_desc, emails, phones

def db_conn_str():
    # DATABASE_URL: postgresql+psycopg://user:pass@postgres:5432/db
    # psycopg espera: postgresql://user:pass@postgres:5432/db
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set")
    return DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)

def insert_page(url: str, title: str, meta_description: str, emails: str, phones: str):
    conninfo = db_conn_str()
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pages (url, title, meta_description, emails, phones)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (url, title, meta_description, emails, phones),
            )
        conn.commit()

def main():
    print("worker: started, waiting jobs:queue")
    while True:
        item = r.blpop("jobs:queue", timeout=30)
        if not item:
            continue

        _, raw = item
        try:
            job = json.loads(raw)
            url = job["url"]
        except Exception as e:
            print("worker: bad job payload:", raw, "err:", e)
            continue

        print("worker: job url:", url)
        try:
            title, meta_desc, emails, phones = scrape_url(url)
            insert_page(url, title, meta_desc, emails, phones)
            print("worker: saved:", url, "title:", title[:80])
        except Exception as e:
            print("worker: FAILED:", url, "err:", e)
            # opcional: guardar fallos en otra lista
            r.rpush("jobs:failed", raw)
            time.sleep(1)

if __name__ == "__main__":
    main()

