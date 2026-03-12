# OpenClawd VPS – HANDOFF
> **Contrato técnico vivo** — única fuente de verdad del sistema.  
> Cualquier cambio arquitectónico (servicio, env var, tabla, flujo) DEBE reflejarse aquí.  
> Last updated: 2026-03-02  

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-28 | Initial stack: oc_api + oc_worker + Postgres + Redis | Alberto |
| 2026-02-28 | Hardened `ops/runner.sh` (flock, jq, safe copy, URL filter) | Antigravity |
| 2026-02-28 | Added `oc_exporter` microservice (port 8001, Google Sheets export) | Antigravity |
| 2026-02-28 | Added `export_checkpoints` table, env vars EXPORTER_TOKEN + SHEETS_* | Antigravity |
| 2026-02-28 | Created this HANDOFF.md as living technical contract | Antigravity |
| 2026-02-28 | Added `oc_control` microservice (port 8081, WhatsApp agent control) | Antigravity |
| 2026-02-28 | Added `control_logs` table, env vars CONTROL_TOKEN + ALLOWED_NUMBERS | Antigravity |
| 2026-03-02 | Linked WhatsApp Business (+34663103334) via OpenClaw gateway | Antigravity |
| 2026-03-02 | Created systemd service `openclaw-gateway.service` | Antigravity |
| 2026-03-02 | Updated ALLOWED_NUMBERS to personal number (34605693177) | Antigravity |
| 2026-03-02 | Added Operational Policy (no Cloud Code dependency) + RUNBOOK.md | Antigravity |
| 2026-03-02 | Added `ops/wa_watchdog.sh` — hourly WhatsApp auto-recovery cron | Antigravity |
| 2026-03-02 | Added Telegram channel `@OpenCrawNexusBot` as backup agent channel | Antigravity |
| 2026-03-04 | Re-linked WhatsApp after rate limit cleared; added `ops/scrub_companies.py` | Antigravity |
| 2026-03-04 | Created `payments` tab in Google Sheet (56 firms, 15-col schema, LatAm M&A) | Antigravity |
| 2026-03-04 | Deprecated `sheets_bridge` — `oc_exporter` + gspread already covers Sheets | Antigravity |
| 2026-03-04 | Added `ops/linkedin_search.py` + `linkedin_search.sh` — SerpAPI autonomous search | Antigravity |
| 2026-03-04 | Added `SERPAPI_KEY` to `.env` (SerpAPI.com); local `linkedin_outreach` updated | Antigravity |
| 2026-03-07 | Enabled OpenClaw `!` elevated mode for deterministic, zero-hallucination WhatsApp/Telegram API | Antigravity |
| 2026-03-07 | Deployed Mission Control (Phase 5): Portainer, Grafana, RedisInsight via Tailscale IP `100.71.50.105` | Antigravity |
| 2026-03-09 | [V5] Document Generator: WeasyPrint PDF engine + `generate-doc.sh` skill with WhatsApp file attachment | Antigravity |
| 2026-03-10 | [V5] Admin self-healing: `admin-ops.sh` skill (status/restart-gateway/restart-docker/fix-all) via chat | Antigravity |
| 2026-03-10 | [V5] Document Generator: Added DOCX generation (`python-docx`) + both PDF and DOCX delivered via WhatsApp | Antigravity |
| 2026-03-10 | [V5] Email Discovery: Enhanced SerpAPI to parse AI Overview, Knowledge Graph, answer_box + multi-query search | Antigravity |
| 2026-03-10 | [V5] System prompt hardened: explicit prohibition against privacy refusals, Pandoc, ZIP, external services | Antigravity |
| 2026-03-10 | [V5] Folder structure: `drafts/`, `plantillas/`, `revision/`, `enviados/` on VPS + local | Antigravity |
| 2026-03-10 | [V5] ARCHITECTURE.md created: full stack architecture doc with 6 data flows + scaling guide | Antigravity |
| 2026-03-10 | [V5] Added HUNTER_API_KEY + ZEROBOUNCE_API_KEY to VPS + local .env. Full email waterfall operational | Antigravity |
| 2026-03-10 | [V5] Improved SerpAPI: AI Overview, Knowledge Graph parsing + multi-query. Permutation engine: 7 patterns + ZeroBounce validation | Antigravity |
| 2026-03-10 | [V5] New skill: `linkedin-sheets.sh` — reads companies from Sheet tab, searches LinkedIn via SerpAPI, writes URLs back to Sheet | Antigravity |
| 2026-03-12 | [V6] Command Router: local Python service replacing cloud agent approvals. Log tailing, subprocess execution, systemd service | Antigravity |

---

## 1. Goal

Automated outreach platform running on a VPS:
1. **Crawl** target company websites → extract contacts (emails, phones, forms)
2. **Export** structured data to Google Sheets
3. **Control** the agent via WhatsApp (whitelist-only channel)
4. *(future)* Send outreach emails via Resend / SMTP-IMAP (nexusfinlabs.com)
5. *(future)* Find LinkedIn profiles (existing project in SW_AI)

---

## 2. Target Verticals

| Vertical | Status | Notes |
|----------|--------|-------|
| **M&A (Texas)** | 🟢 Active | ~210+ pages crawled |
| Pharma | 🔜 Planned | GxP / AI Act context |
| Telco | 🔜 Planned | |
| Industrial | 🔜 Planned | |
| SaaS | 🔜 Planned | |

---

## 3. VPS & Infrastructure

- **Host alias**: `openclawd-vps`
- **User**: `albi_agent`
- **Stack path**: `~/openclawd_stack`
- **Deploy from Mac**: `./deploy.sh` (rsync + docker compose up)

### Docker Containers (Core Stack - `~/openclawd_stack/docker-compose.yml`)

| Container | Image / Build | Port | Purpose |
|-----------|--------------|------|---------|
| `oc_postgres` | `postgres:16-alpine` | internal | Database |
| `oc_redis` | `redis:7-alpine` | internal | Job queue |
| `oc_api` | `./app` | `8000` | Crawler API (FastAPI) |
| `oc_worker` | `./app` | — | Redis queue consumer + scraper |
| `oc_exporter` | `./exporter` | `8001` | Sheets exporter (FastAPI) |
| `oc_control` | `./control` | `8081` | WhatsApp agent control (FastAPI) |

### Docker Containers (Mission Control - `~/openclawd_stack/monitoring/docker-compose.yml`)

| Container | Image | Port | Purpose | Navigation |
|-----------|-------|------|---------|------------|
| `portainer` | `portainer/portainer-ce` | `9000` | Docker orchestration GUI | `http://100.71.50.105:9000` |
| `grafana` | `grafana/grafana` | `3000` | Analytics & Alerts dashboard | `http://100.71.50.105:3000` |
| `redisinsight` | `redis/redisinsight` | `5540` | Redis queue inspection GUI | `http://100.71.50.105:5540` |
| `webtop` | `linuxserver/webtop:ubuntu-xfce` | `6080` | Web Desktop (NoVNC + XFCE4) | `http://100.71.50.105:6080` |
| `prometheus` | `prom/prometheus` | `9091` | Metrics scraper & time-series DB | internal |
| `node_exporter` | `prom/node-exporter` | `9100` | Host hardware metrics | internal |

### Native Services (non-Docker)

| Service | Binary | Ports | Purpose |
|---------|--------|-------|---------|
| `openclaw-gateway` | `openclaw gateway` | `18789` (UI+WS), `18791` (browser API) | OpenClaw AI agent + WhatsApp channel |
| `command-router` | `python3 ops/command_router.py` | — (log tailer) | Local `!` command executor (no cloud agent) |
| `cockpit` | `systemctl` | `9090` | Ubuntu Server web GUI + File browser |

Status check:
```bash
sudo docker ps --format "table {{.Names}}\t{{.Status}}"
```

---

## 4. Database (Postgres)

User/DB: `openclawd` / `openclawd`

### Tables

**pages** (created by oc_api on startup)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| url | TEXT | Crawled URL |
| title | TEXT | Page title |
| meta_description | TEXT | Meta description |
| emails | TEXT | CSV of emails found |
| phones | TEXT | CSV of phones found |
| forms | TEXT | JSON string of forms |
| fetched_at | TIMESTAMPTZ | Default now() |

**export_checkpoints** (created by oc_exporter on startup)
| Column | Type | Notes |
|--------|------|-------|
| name | TEXT PK | e.g. "pages" |
| last_id | INTEGER | Last exported page ID |
| updated_at | TIMESTAMPTZ | Last export time |

**control_logs** (created by oc_control on startup)
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | Auto-increment |
| sender | TEXT | Phone number (without +) |
| command | TEXT | Command received |
| response | TEXT | Response sent (capped 4k) |
| created_at | TIMESTAMPTZ | Default now() |

Quick checks:
```bash
ssh -t openclawd-vps "sudo docker exec -it oc_postgres psql -U openclawd -d openclawd -c '\dt'"
ssh -t openclawd-vps "sudo docker exec -it oc_postgres psql -U openclawd -d openclawd -c 'SELECT count(*) FROM pages;'"
ssh -t openclawd-vps "sudo docker exec -it oc_postgres psql -U openclawd -d openclawd -c 'SELECT * FROM export_checkpoints;'"
```

---

## 5. Services Detail

### 5.1 oc_api (Crawler API – port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | DB + Redis check |
| `/jobs` | POST | Queue a URL for scraping (`{"url":"...","note":"..."}`) |
| `/pages` | GET | List scraped pages (limit=50) |

### 5.2 oc_worker

Consumes jobs from Redis queue `jobs:queue`. Scrapes URL using `requests` + `BeautifulSoup`, saves to `pages` table. Retries up to 3x with backoff. Skips non-retryable errors (DNS, SSL).

### 5.3 oc_exporter (Sheets Exporter – port 8001)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | DB + Sheets connectivity |
| `/status` | GET | No | Checkpoint positions + page counts |
| `/export/pages` | POST | Bearer | Incremental export to `companies` tab |
| `/export/events` | POST | Bearer | Log snapshot event to `events` tab |

Auth: `Authorization: Bearer $EXPORTER_TOKEN`

**Export flow** (`/export/pages`):
1. Read checkpoint `last_id` from `export_checkpoints`
2. Query pages with `id > last_id` (limit param, default 200)
3. Append rows to Google Sheet `companies` tab
4. Update checkpoint to new `last_id`
5. No duplicates: checkpoint is the guard

**Curl test commands:**
```bash
# Health (no auth)
curl http://localhost:8001/health

# Status (no auth)
curl http://localhost:8001/status

# Export pages (auth required, run on VPS)
curl -X POST -H "Authorization: Bearer $EXPORTER_TOKEN" \
  "http://localhost:8001/export/pages?limit=50"

# Export events (auth required)
curl -X POST -H "Authorization: Bearer $EXPORTER_TOKEN" \
  "http://localhost:8001/export/events"

# Auth failure test (should return 401)
curl -X POST "http://localhost:8001/export/pages"
```

### 5.4 Runner (cron – ops/runner.sh)

Cron-safe script that processes one URL per invocation:
- `flock` on `state/runner.lock` → no parallel runs
- Copies `targets.txt` → `_work.targets` (never writes to original)
- Filters only `^https://` lines
- Uses `jq` for safe JSON construction
- Logs with timestamps to `state/runner.log`

### 5.5 oc_control (WhatsApp Agent Control – port 8081)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | DB connectivity |
| `/whatsapp` | POST | Main webhook from OpenClaw |

**Whitelist**: Only numbers in `ALLOWED_NUMBERS` can interact.

**Commands:**
| Command | Description |
|---------|-------------|
| `help` | Show available commands |
| `status` | Health of all services (API, Exporter, Postgres) |
| `pages` | Page stats: total, with emails, exported, pending |
| `health` | Detailed health check of every component |
| `export` | Trigger incremental export to Google Sheets |
| `scrape <url>` | Queue URL for scraping via oc_api |
| `logs` | Last 5 WhatsApp interactions |

**Security:**
- No shell execution — uses `httpx` to call internal APIs
- Every interaction logged to `control_logs` table
- Unauthorized numbers silently ignored

### 5.6 OpenClaw Gateway (WhatsApp AI Agent)

**Not a Docker container** — runs natively on VPS as a systemd service.

| Field | Value |
|-------|-------|
| Binary | `/home/albi_agent/.nvm/versions/node/v22.22.0/bin/node openclaw.mjs gateway` |
| Config | `~/.openclaw/openclaw.json` |
| Auth profiles | `~/.openclaw/agents/main/agent/auth-profiles.json` |
| WhatsApp sessions | `~/.openclaw/credentials/whatsapp-default/` |
| Log file | `/tmp/openclaw/openclaw-YYYY-MM-DD.log` |
| Systemd | `openclaw-gateway.service` |
| UI port | `18789` (localhost only, access via SSH tunnel) |
| API port | `18791` (browser control) |

**Architecture:**
```
Tu WhatsApp Personal (+34605693177)
        ↕ messages
WhatsApp Business (+34663103334) ← linked to OpenClaw via QR
        ↕ Baileys protocol
OpenClaw Gateway (VPS, port 18789)
        ↕ AI agent (OpenRouter/auto model)
Responds via WhatsApp Business
```

**WhatsApp channel config** (`~/.openclaw/openclaw.json`):
```json
"channels": {
  "whatsapp": {
    "enabled": true,
    "dmPolicy": "pairing",
    "groupPolicy": "allowlist"
  }
}
```

**Key operations:**
```bash
# Check gateway status
sudo systemctl status openclaw-gateway

# View live logs
journalctl -u openclaw-gateway -f

# Restart gateway
sudo systemctl restart openclaw-gateway

# Access Web UI (from Mac)
ssh -fN -L 18789:localhost:18789 openclawd-vps
# Then open: http://localhost:18789/?token=<GATEWAY_TOKEN>

# Approve new WhatsApp sender
export PATH=$HOME/.nvm/versions/node/v22.22.0/bin:$PATH
openclaw pairing approve whatsapp <CODE>

# Check WhatsApp connection
grep -i whatsapp /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | tail -5
```

**Deterministic Channel API (Zero Hallucinations) 🚀**:
To ensure critical commands (like running scrapes on specific rows) are never misinterpreted by the LLM, we use OpenClaw's `!` elevated bash logic.
- The user sends: `! ~/job <task> <args...>` (e.g. `! ~/job linkedin TEST_OPENCLAW payments 10-12`)
- The Gateway intercepts the `!` and immediately executes the `~/job` bash script on the VPS host, completely bypassing the AI model.
- The `~/job` script acts as an API router, mapping the command to the correct internal script (e.g. `search-linkedin.sh`), enqueues it in Redis via `oc_control`, and returns a JSON confirmation instantly to the chat.
- Prerequisite: User's chat ID must be whitelisted in `tools.elevated.allowFrom` in `openclaw.json` AND `exec-approvals.json` must be configured to unconditionally allow `~/job`.

> [!IMPORTANT]
> **OpenClaw config gotcha**: `openclaw config set` validates each field independently.
> Setting `dmPolicy` and `allowFrom` one at a time causes validation errors.
> **Always edit `~/.openclaw/openclaw.json` directly** when changing multiple related fields:

```bash
# Correct way to update OpenClaw WhatsApp config (both fields at once):
ssh -t openclawd-vps "python3 -c \"
import json
with open('/home/albi_agent/.openclaw/openclaw.json') as f:
    c = json.load(f)
c['channels']['whatsapp']['dmPolicy'] = 'allowlist'
c['channels']['whatsapp']['allowFrom'] = ['34605693177@s.whatsapp.net']
with open('/home/albi_agent/.openclaw/openclaw.json', 'w') as f:
    json.dump(c, f, indent=2)
print('Config updated OK')
\""
```

**Full WhatsApp re-link procedure** (if session expires or WA stops responding):
```bash
# Step 1: Update config (both fields at once via JSON)
ssh -t openclawd-vps "python3 -c \"
import json
with open('/home/albi_agent/.openclaw/openclaw.json') as f:
    c = json.load(f)
c['channels']['whatsapp']['dmPolicy'] = 'allowlist'
c['channels']['whatsapp']['allowFrom'] = ['34605693177@s.whatsapp.net']
with open('/home/albi_agent/.openclaw/openclaw.json', 'w') as f:
    json.dump(c, f, indent=2)
print('Config updated OK')
\" && export PATH=\$HOME/.nvm/versions/node/v22.22.0/bin:\$PATH && \
systemctl --user restart openclaw-gateway && \
sleep 3 && openclaw channels login --channel whatsapp --verbose"
# Wait for: "WhatsApp Web connected." — let the command finish on its own (no Ctrl+C)
```

**Phone numbers:**
| Number | Role | Notes |
|--------|------|-------|
| +34663103334 | Agent (WhatsApp Business) | Linked to OpenClaw, sends/receives as the bot |
| +34605693177 | Owner (WhatsApp Personal) | Approved sender, interacts with agent |

### 5.7 Command Router (Local `!` Command Executor)

**Not a Docker container** — runs natively on VPS as a systemd service.
Replaces the cloud agent approval system for deterministic command execution.

| Field | Value |
|-------|-------|
| Script | `ops/command_router.py` |
| Systemd | `command-router.service` |
| Log file | `/tmp/command_router.log` |
| Mechanism | Tails gateway log, parses `web-inbound` JSON messages |
| Dependencies | None (stdlib only) |

**Architecture:**
```
WhatsApp → Gateway → log file → command_router.py → subprocess → scripts → openclaw message send
```

**Command Map:**

| Command | Script | Example |
|---------|--------|---------|
| `!make-proposal` | `make-proposal.sh` | `!make-proposal john@co.com AI strategy` |
| `!send-proposal` | `send-proposal.sh` | `!send-proposal john@co.com` |
| `!busca-email` | `enrich-email.sh` | `!busca-email Juan Perez acme.com` |
| `!busca-linkedin` | `linkedin-sheets.sh` | `!busca-linkedin vc_payments 4 10` |
| `!admin` | `admin-ops.sh` | `!admin status` / `!admin fix-all` |
| `!generate-doc` | `generate-doc.sh` | `!generate-doc SOW "content..."` |
| `!draft-email` | `draft-email.sh` | `!draft-email "Acme" target@acme.com` |
| `!calendar-status` | `calendar-status.sh` | `!calendar-status meeting` |
| `!calendar-create` | `calendar-create-event.sh` | `!calendar-create "Call" "2026-03-15T16:00Z" "a@b.com"` |
| `!calendar-from-email` | `calendar-from-email.sh` | `!calendar-from-email "speaker name"` |
| `!calendar-upload` | `calendar-upload-ics.sh` | `!calendar-upload /tmp/event.ics` |
| `!help` | (built-in) | Shows all available commands |

**Email Enrichment Waterfall** (`!busca-email`):
```
1. Hunter.io (API)
2. Snov.io (API)
3. Web Scraping (mailto: links on company pages)
4. SerpAPI Google Search (AI Overview, Knowledge Graph, organic results)
5. Smart Permutation Engine (first.last@, flast@, etc.) + ZeroBounce validation
```

**Calendar from Email** (`!calendar-from-email`):
Searches IMAP inboxes (Gmail + IONOS) for emails matching the query,
extracts `.ics` attachments, and adds them to Google Calendar automatically.

**Service management:**
```bash
sudo systemctl status command-router
sudo systemctl restart command-router
cat /tmp/command_router.log
```

---

## 6. Google Sheets

| Field | Value |
|-------|-------|
| Spreadsheet | TEST_OPENCLAW |
| Spreadsheet ID | `1_GwMkz8niCS8Uz_yh8fTU9AFVOGfzDFkd4L8glzfrUM` |
| Tabs | `companies`, `prospects`, `outreach`, `events` |
| Service Account | `test-indeed@oauth2-453404.iam.gserviceaccount.com` |
| Credentials (VPS) | `/home/albi_agent/.secrets/google/credentials.json` |

**Important**: Sheet must be shared with the service account email as Editor.

---

## 7. Environment Variables

### .env locations

| Location | Purpose |
|----------|---------|
| **Local**: `vault/.env` | Source of truth — all secrets, not in git. Edit here, then deploy. |
| **VPS**: `~/openclawd_stack/.env` | Deployed copy — loaded by Docker and ops scripts. |

> [!IMPORTANT]
> To run ops scripts on the VPS (e.g. `scrub_companies.py`), load env vars with:
> ```bash
> cd ~/openclawd_stack && set -a && source .env && set +a
> export GOOGLE_APPLICATION_CREDENTIALS=/home/albi_agent/.secrets/google/credentials.json
> ```

### Variable Reference

| Variable | Used by | Description |
|----------|---------|-------------|
| `DATABASE_URL` | api, worker, exporter | Postgres connection string |
| `REDIS_URL` | api, worker | Redis connection string |
| `POSTGRES_PASSWORD` | postgres | DB password |
| `OPENROUTER_API_KEY` | OpenClaw gateway | LLM (also in `~/.openclaw/agents/main/agent/auth-profiles.json`) |
| `OPENAI_API_KEY` | OpenClaw gateway | Fallback LLM |
| `EXPORTER_TOKEN` | exporter, control | Bearer token for POST endpoints |
| `SHEETS_SPREADSHEET_ID` | exporter, scrubber | Google Sheet ID |
| `SHEETS_TAB_EVENTS` | exporter | Tab name for events |
| `SHEETS_TAB_COMPANIES` | exporter, scrubber | Tab name for companies |
| `GOOGLE_APPLICATION_CREDENTIALS` | exporter, scrubber | **Docker container**: `/secrets/google/credentials.json`<br>**VPS native**: `/home/albi_agent/.secrets/google/credentials.json` |
| `CONTROL_TOKEN` | control | Internal auth token |
| `ALLOWED_NUMBERS` | control | Whitelisted phone numbers (`34605693177`) |
| `APOLLO_API_KEY` | email_enricher | Fallback 1 for email enrichment |
| `HUNTER_API_KEY` | email_enricher | Fallback 2 for email enrichment |
| `ZEROBOUNCE_API_KEY` | email_enricher | Email validation check |
| `SMTP_SERVER / IMAP_*` | email_sender | IONOS servers |
| `EMAIL_SENDER` | email_sender | **DEPRECATED** (Using dual personas now) |
| `EMAIL_PASS_NEXUS` | email_sender | Password for `hola@nexusfinlabs.com` |
| `EMAIL_PASS_IAGROWTH` | email_sender | Password for `sales@iagrowth.io` |
| `PORTAINER_USER/PASSWORD` | monitoring | Portainer initial admin credentials |
| `GRAFANA_USER/PASSWORD` | monitoring | Grafana initial admin credentials |
| `CHROME_KEYRING_PASS` | Desktop (VNC) | Password for the NoVNC Chrome/Chromium Keyring lock |

---

## 8. File Structure

```
openclawd_stack/
├── docker-compose.yml          # All services
├── .env                        # Env vars (secret, not in git)
├── app/                        # Crawler API + Worker
│   ├── Dockerfile
│   ├── main.py                 # FastAPI: /health, /jobs, /pages
│   ├── worker.py               # Redis consumer + scraper
│   ├── scrape.py               # requests + BeautifulSoup
│   ├── models.py               # Page model
│   ├── db.py                   # SQLAlchemy setup
│   └── requirements.txt
├── exporter/                   # Sheets Exporter
│   ├── Dockerfile
│   ├── main.py                 # FastAPI: /health, /status, /export/*
│   ├── models.py               # Page (read-only) + ExportCheckpoint
│   ├── db.py                   # SQLAlchemy setup
│   ├── sheets.py               # gspread wrapper
│   ├── auth.py                 # Bearer token auth
│   └── requirements.txt
├── control/                    # WhatsApp Agent Control (NEW)
│   ├── Dockerfile
│   ├── main.py                 # FastAPI: /health, /whatsapp
│   ├── models.py               # ControlLog + Page (read-only)
│   ├── db.py                   # SQLAlchemy setup
│   └── requirements.txt
├── migrations/
│   ├── 001_export_checkpoints.sql
│   └── 002_control_logs.sql
├── ops/
│   ├── runner.sh               # Cron runner (flock, jq, safe copy)
│   ├── make_targets.sh
│   ├── watchdog.sh
│   ├── wa_watchdog.sh          # WhatsApp 24/7 auto-recovery (cron hourly)
│   ├── scrub_companies.py      # Company URL quality scrubber → writes STATUS to Sheets
│   ├── email_enricher.py       # Discovery waterfall (Apollo -> Hunter -> ZeroBounce)
│   ├── email_drafter.py        # Multi-LLM drafter dynamically loading persona context
│   ├── email_sender.py         # Dynamic IONOS SMTP sender based on persona
│   ├── email_style_guide.json  # Tones, rules and signatures for dual accounts
│   └── openclaw_skills/
│       ├── draft-email.sh      # OpenClaw skill wrapper
│       ├── enrich-email.sh     # OpenClaw skill wrapper for email_enricher
│       ├── generate-doc.sh     # [V5] Document generator: Draft -> WeasyPrint PDF -> WhatsApp delivery
│       └── admin-ops.sh        # [V5] Self-healing admin: status, restart-gateway, restart-docker, fix-all
└── state/                      # Runtime state (on VPS only)
    ├── targets.txt
    ├── done.txt
    ├── failed.txt
    ├── runner.lock
    └── runner.log
```

---

## 9. Deploy

```bash
# From Mac (project/ directory)
./deploy.sh
```

This rsyncs `openclawd_stack/` to VPS (excluding `.env` and `vault/`), then runs `docker compose up -d --build`.

**After deploy, on VPS:**
```bash
# Ensure EXPORTER_TOKEN is set in .env
# Then trigger first export:
curl -X POST -H "Authorization: Bearer $EXPORTER_TOKEN" "http://localhost:8001/export/pages?limit=200"
```

---

## 10. Constraints & Safety

- **NEVER** commit `.env` or `credentials.json`
- Local secrets: `vault/.env` and `vault/credentials.json`
- VPS secrets: `~/openclawd_stack/.env` + `/home/albi_agent/.secrets/google/credentials.json`
- When adding env vars on VPS → also add to local `vault/.env`

---

## 11. Web Desktop (GUI)

The VPS has a manual XFCE4 graphical environment installed for browser-based debugging (like Chrome/Chromium). It is accessible via Tailsale.

| Component | Port | Access |
|-----------|------|--------|
| `websockify` + `noVNC` | `6080` | `http://100.71.50.105:6080/vnc.html` |
| `tightvncserver` | `5901` | internal loopback |

**To Manually Start the Desktop:**
```bash
vncserver :1
websockify -D --web=/usr/share/novnc/ 6080 localhost:5901
```

**Chrome Keyring Password Prompt:**
When launching Chrome on a headless XFCE4 desktop, it often prompts for a "Keyring / Keychain Password". 
- The password to enter is defined in `.env` as `CHROME_KEYRING_PASS`.
- Alternatively, you can launch Chrome via terminal bypassing the keyring entirely:
  ```bash
  google-chrome --password-store=basic
  # or
  chromium-browser --password-store=basic
  ```

---

## 12. Future Roadmap

| Feature | Tool | Status |
|---------|------|--------|
| Email outreach | Resend API or SMTP/IMAP (ionos, nexusfinlabs.com) | 🔜 |
| LinkedIn profiles | Existing SW_AI project (linkedin_outreach / linkedin_payments) | 🔜 |
| WhatsApp AI agent | OpenClaw gateway + WhatsApp Business | 🟢 Live |
| WhatsApp control commands | oc_control webhook from OpenClaw | � Connect webhook |
| More verticals | Pharma, Telco, Industrial, SaaS | 🔜 |
| Scheduled exports | Cron or scheduler for oc_exporter | 🔜 |

---

## 12. Operational Policy — Antigravity vs Cloud Code (IMPORTANT)

> [!CAUTION]
> Antigravity MUST NOT run strategies that depend on Google Cloud Code (`cloudcode-pa.googleapis.com`) as the primary execution path.

**Reason:**
- Cloud Code can return `503 MODEL_CAPACITY_EXHAUSTED` and becomes a single point of failure.
- Production must remain operational even when Cloud Code has no model capacity.

**Required approach:**
- Antigravity is used **ONLY** as: editor + terminal runner + deploy/orchestration UI.
- All "agent brain" / reasoning must run on the VPS via **OpenClaw Gateway**.
- LLM routing is handled by OpenClaw:
  - **Primary**: OpenRouter (auto/balanced)
  - **Fallback**: OpenAI (gpt-4.1-mini / gpt-4o-mini)

**Allowed execution paths:**
```
✅ Antigravity terminal → SSH to VPS → call oc_api / oc_exporter / oc_control
✅ WhatsApp → OpenClaw Gateway → oc_control webhook
```

**Disallowed execution paths:**
```
❌ Any Antigravity strategy that calls Google Cloud Code as the primary LLM runtime.
```

**See also:** `RUNBOOK.md` for all operational commands.
