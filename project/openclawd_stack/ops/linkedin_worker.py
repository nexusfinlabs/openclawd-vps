#!/usr/bin/env python3
"""
ops/linkedin_worker.py
======================
Polls Redis queue for LinkedIn search jobs pushed by oc_control.
Runs linkedin_search.py for each job. Designed to run permanently on VPS host.

Start: nohup python3 ops/linkedin_worker.py >> logs/linkedin_worker.log 2>&1 &
"""
import os, json, time, subprocess, sys
from pathlib import Path

# Load .env
def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_env()

import redis

REDIS_URL   = os.getenv("REDIS_URL", "redis://localhost:6379/0")
JOB_QUEUE   = "oc:jobs:linkedin"
RESULT_QUEUE = "oc:results:linkedin"

BASE_DIR    = Path(__file__).parent.parent
SEARCH_SCRIPT = BASE_DIR / "ops" / "linkedin_search.py"
LOG_DIR     = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

def _notify_chat(message, channel="whatsapp", target="34605693177"):
    """Send a notification back to the user's chat channel via openclaw CLI."""
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
        print(f"[worker] Failed to send chat notification: {e}", flush=True)


def run_job(job: dict) -> tuple[str, str]:
    """Run linkedin_search.py and return (status, output_tail)."""
    tab      = job.get("tab", "payments")
    top_rows = job.get("top_rows")
    start_row = job.get("start_row")
    end_row   = job.get("end_row")

    cmd = [
        sys.executable, str(SEARCH_SCRIPT),
        "--tab", tab,
    ]
    if top_rows:
        cmd += ["--top-rows", str(top_rows)]
    if start_row:
        cmd += ["--start-row", str(start_row)]
    if end_row:
        cmd += ["--end-row", str(end_row)]

    env = os.environ.copy()
    env["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path.home() / ".secrets/google/credentials.json")

    log_path = LOG_DIR / "linkedin_search.log"
    print(f"[worker] Running: {' '.join(cmd)}", flush=True)

    with open(log_path, "a") as log_f:
        proc = subprocess.run(
            cmd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=600,   # 10 min max per job
        )
        # Also write to log file
        if proc.stdout:
            log_f.write(proc.stdout)

    # Extract last meaningful lines for the notification
    output_tail = ""
    if proc.stdout:
        lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
        output_tail = "\n".join(lines[-5:])  # last 5 lines

    status = "ok" if proc.returncode == 0 else f"error (code {proc.returncode})"
    return status, output_tail


def main():
    print(f"[linkedin_worker] Starting — polling {REDIS_URL} / queue={JOB_QUEUE}", flush=True)
    r = redis.from_url(REDIS_URL, decode_responses=True)

    while True:
        try:
            # Blocking pop — waits up to 10s for a job
            item = r.blpop(JOB_QUEUE, timeout=10)
            if not item:
                continue

            _, raw = item
            job = json.loads(raw)
            job_id = job.get("job_id", "?")
            channel = job.get("channel", "whatsapp")
            target = job.get("target", "34605693177")
            print(f"[worker] Job {job_id}: {job}", flush=True)

            result, output_tail = run_job(job)
            print(f"[worker] Job {job_id} finished: {result}", flush=True)

            # Push result to Redis (optional, for oc_control)
            r.setex(f"oc:linkedin_result:{job_id}", 300, json.dumps({
                "job_id": job_id,
                "status": result,
                "tab": job.get("tab", "payments"),
                "top_rows": job.get("top_rows"),
            }))

            # Notify the user on their original channel
            tab = job.get("tab", "payments")
            rows_desc = f"{job.get('start_row', '?')}-{job.get('end_row', '?')}"
            if result == "ok":
                msg = (
                    f"✅ LinkedIn search completado\n"
                    f"• Job: `{job_id}` | Tab: `{tab}` | Rows: `{rows_desc}`\n"
                )
                if output_tail:
                    msg += f"\n```\n{output_tail[:500]}\n```"
            else:
                msg = (
                    f"❌ LinkedIn search falló\n"
                    f"• Job: `{job_id}` | Tab: `{tab}` | Rows: `{rows_desc}`\n"
                    f"• Status: `{result}`\n"
                )
                if output_tail:
                    msg += f"\n```\n{output_tail[:500]}\n```"

            _notify_chat(msg, channel=channel, target=target)

        except KeyboardInterrupt:
            print("[worker] Stopping.", flush=True)
            break
        except Exception as e:
            print(f"[worker] Error: {e}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
