# RUNBOOK — OpenClawd (NO Cloud Code)

> All reasoning/LLM runs on VPS via OpenClaw Gateway.
> Antigravity = editor + terminal + deploy only.
> If Cloud Code fails (503), ignore it. Operate via OpenClaw + oc_* services.

---

## Quick commands (from Mac terminal)

```bash
# Health check
ssh openclawd-vps "curl -s http://localhost:8081/health | python3 -m json.tool"

# Status (via oc_control webhook, simulates WhatsApp "status" command)
ssh openclawd-vps 'curl -s -X POST http://localhost:8081/whatsapp -H "Content-Type: application/json" -d "{\"from\":\"34605693177\",\"message\":\"status\"}" | python3 -m json.tool'

# Pages stats
ssh openclawd-vps 'curl -s -X POST http://localhost:8081/whatsapp -H "Content-Type: application/json" -d "{\"from\":\"34605693177\",\"message\":\"pages\"}" | python3 -m json.tool'

# Export to Sheets (up to N pages)
ssh openclawd-vps 'curl -s -X POST -H "Authorization: Bearer $EXPORTER_TOKEN" "http://localhost:8001/export/pages?limit=50" | python3 -m json.tool'

# Scrape a URL
ssh openclawd-vps 'curl -s -X POST http://localhost:8000/jobs -H "Content-Type: application/json" -d "{\"url\":\"https://example.com\",\"note\":\"manual\"}" | python3 -m json.tool'

# View last control logs
ssh openclawd-vps 'curl -s -X POST http://localhost:8081/whatsapp -H "Content-Type: application/json" -d "{\"from\":\"34605693177\",\"message\":\"logs\"}" | python3 -m json.tool'
```

---

## Docker stack

```bash
# Container status
ssh openclawd-vps "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# Logs for any container
ssh openclawd-vps "docker logs oc_api --tail 30 2>&1"
ssh openclawd-vps "docker logs oc_worker --tail 30 2>&1"
ssh openclawd-vps "docker logs oc_exporter --tail 30 2>&1"
ssh openclawd-vps "docker logs oc_control --tail 30 2>&1"

# Restart a service
ssh -t openclawd-vps "cd ~/openclawd_stack && sudo docker compose restart api"

# Full rebuild + deploy (from Mac)
cd ~/Desktop/SW_AI/openclawd-vps/project && ./deploy.sh
```

---

## OpenClaw Gateway (WhatsApp)

```bash
# Systemd status
ssh openclawd-vps "systemctl --user status openclaw-gateway"

# Live logs
ssh openclawd-vps "journalctl --user -u openclaw-gateway -f"

# Restart gateway
ssh openclawd-vps "systemctl --user restart openclaw-gateway"

# WhatsApp connection check
ssh openclawd-vps "grep -i 'whatsapp\|Listening\|disconnect\|error' /tmp/openclaw/openclaw-\$(date +%Y-%m-%d).log | tail -10"

# Re-link WhatsApp (if session expired)
ssh -t openclawd-vps "export PATH=\$HOME/.nvm/versions/node/v22.22.0/bin:\$PATH && openclaw channels login --channel whatsapp"

# Access Web UI (SSH tunnel, then open browser)
ssh -fN -L 18789:localhost:18789 openclawd-vps
# → http://localhost:18789
```

### Deterministic Channel API (via `!`)
To execute commands reliably from WhatsApp or Telegram *without* LLM hallucination:
```text
! ~/job linkedin <document> <tab> <rows>
# Example: ! ~/job linkedin TEST_OPENCLAW payments 10-12
```
This bypasses `openclaw-gateway` AI capabilities and executes `~/job` directly on the host, which queues the task into Redis.

---

## Database

```bash
# Page count
ssh openclawd-vps "docker exec oc_postgres psql -U openclawd -d openclawd -tAc 'SELECT count(*) FROM pages;'"

# Export checkpoint
ssh openclawd-vps "docker exec oc_postgres psql -U openclawd -d openclawd -tAc 'SELECT * FROM export_checkpoints;'"

# Recent pages
ssh openclawd-vps "docker exec oc_postgres psql -U openclawd -d openclawd -c 'SELECT id,url,title FROM pages ORDER BY id DESC LIMIT 5;'"

# Control logs
ssh openclawd-vps "docker exec oc_postgres psql -U openclawd -d openclawd -c 'SELECT id,sender,command,status,created_at FROM control_logs ORDER BY id DESC LIMIT 10;'"
```

---

## LLM Routing (on VPS, via OpenClaw)

| Priority | Provider | Model | Notes |
|----------|----------|-------|-------|
| Primary | OpenRouter | auto/balanced | `~/.openclaw/agents/main/agent/auth-profiles.json` |
| Fallback | OpenAI | gpt-4.1-mini / gpt-4o-mini | Same auth-profiles.json |

**Antigravity NEVER calls Cloud Code as primary LLM runtime.**

---

## Troubleshooting

| Symptom | Check | Fix |
|---------|-------|-----|
| WhatsApp not responding | `grep disconnect` in gateway logs | `systemctl --user restart openclaw-gateway` or re-link QR |
| Container down | `docker ps -a` | `docker compose up -d --build` |
| Export fails | `docker logs oc_exporter` | Check EXPORTER_TOKEN, Sheet permissions |
| 503 Cloud Code | Ignore | Operate via SSH + oc_* services |
