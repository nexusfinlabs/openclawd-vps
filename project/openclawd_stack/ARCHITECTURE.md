# 🏗️ OpenClaw Stack — Arquitectura V9

> Documento vivo. Última actualización: 2026-03-13.

---

## 1. Principio Fundamental

```
WhatsApp/Telegram → Gateway (SOLO transporte) → Log File → Command Router (TODA la lógica) → Scripts → openclaw message send
```

**EL GATEWAY NO EJECUTA NADA.** Solo transporta mensajes.
**EL ROUTER EJECUTA TODO.** Es el único que procesa comandos `!`.

---

## 2. Gateway — Qué Hace (MÍNIMO)

**Servicio**: `openclaw-gateway.service` (systemd, Node.js)
**Binario**: `openclaw gateway` (npm package)
**Config**: `/home/albi_agent/.openclaw/openclaw.json`

### Lo que SÍ hace
- Mantiene conexión WhatsApp (Baileys) y Telegram (Bot API)
- Recibe mensajes entrantes de ambos canales
- **Escribe CADA mensaje en** `/tmp/openclaw/openclaw-YYYY-MM-DD.log` (formato JSON)
- Envía mensajes cuando se le pide: `openclaw message send --channel X --target Y --message Z`
- Envía archivos adjuntos: `openclaw message send --media /path/to/file`

### Lo que NO debe hacer (bloqueado en system-prompt.md REGLA #0)
- ❌ NO procesa comandos `!`
- ❌ NO ejecuta scripts
- ❌ NO genera respuestas AI para `!`
- ❌ NO busca en web (`web.search.enabled = false`)

### ⚠️ Tiene un AI agent (NO queremos usarlo para `!`)
El gateway tiene un AI agent (claude-opus vía OpenRouter) con herramienta `exec`.
Para mensajes normales (sin `!`) SÍ responde vía AI.
Para `!` comandos, `system-prompt.md` tiene **REGLA #0** que le ordena IGNORAR.

### Config clave (`openclaw.json`)
```json
{
  "tools.exec.security": "full",
  "tools.exec.ask": "off",
  "tools.web.search.enabled": false,
  "tools.web.fetch.enabled": false,
  "tools.elevated.allowFrom.whatsapp": [],
  "tools.elevated.allowFrom.telegram": [],
  "agents.defaults.model.primary": "anthropic/claude-opus-4-6"
}
```

### Reiniciar
```bash
sudo systemctl restart openclaw-gateway
sudo journalctl -u openclaw-gateway -f  # ver logs
```

---

## 3. Command Router — Qué Hace (TODO)

**Servicio**: `command-router.service` (systemd, Python)
**Archivo**: `ops/command_router.py`
**Working dir**: `/home/albi_agent/openclawd_stack`

### Cómo funciona (paso a paso)
1. **Tail -f** del log del gateway (`/tmp/openclaw/openclaw-YYYY-MM-DD.log`)
2. **Parsea** cada línea JSON buscando mensajes de los senders permitidos
3. **Detecta** si empieza con `!` (e.g. `!make-ppt`, `!analysis`, `!help`)
4. **Ejecuta** el script correspondiente via `subprocess.run(["bash", script_path, ...args])`
5. **Pasa al script** las variables de entorno `SENDER_TARGET` y `SENDER_CHANNEL`
6. **El script** genera output + archivos, y los envía via `openclaw message send`

### Comandos inline (sin script)
- `!help` → devuelve menú de ayuda
- `!context norgine <texto>` → guarda archivo en `/context/norgine.md`
- `!context-list` / `!context-show` / `!context-clear`

### Ruta de scripts: `ops/openclaw_skills/`

| Comando | Script | Función |
|---|---|---|
| `!make-ppt` | `make-ppt.sh` | Presentaciones (PptxGenJS/python-pptx) |
| `!analysis` | `analysis.sh` | Análisis web profundo + LLM |
| `!busca-linkedin` | Async → Redis queue | LinkedIn → Google Sheets |
| `!busca-email` | `enrich-email.sh` | Waterfall: Hunter→Snov→SerpAPI |
| `!make-proposal` | `make-proposal.sh` | Borrador M&A con LLM |
| `!send-proposal` | `send-proposal.sh` | Envía borrador por SMTP |
| `!make-invoice` / `!send-invoice` | `make-invoice.sh` / `send-invoice.sh` | Facturación |
| `!generate-doc` | `generate-doc.sh` | PDF + DOCX (NDA, SOW, etc.) |
| `!draft-email` | `draft-email.sh` | Email M&A estilo Alberto |
| `!calendar-*` | `calendar-*.sh` | Google Calendar ops |
| `!admin` | `admin-ops.sh` | Status / reinicio |

### Paridad WhatsApp/Telegram
El router pasa `SENDER_CHANNEL` al script → el script responde por el MISMO canal.
Todos los `!` commands funcionan **idéntico** en WhatsApp y Telegram.

### Reiniciar (⚠️ USAR SYSTEMD, NUNCA NOHUP)
```bash
sudo systemctl restart command-router
sudo journalctl -u command-router -f  # ver logs
```

> **NUNCA** usar `nohup python3 ops/command_router.py &` — crea duplicados con systemd.

---

## 4. Otros Servicios (systemd)

| Servicio | Función | Restart |
|---|---|---|
| `openclaw-gateway` | Transporte WA/TG | `sudo systemctl restart openclaw-gateway` |
| `command-router` | Ejecutor `!` commands | `sudo systemctl restart command-router` |
| `tg_control` | Bot Telegram (legacy) | `sudo systemctl restart tg_control` |
| `linkedin-worker` | Jobs async LinkedIn (Redis) | `@reboot` crontab |

### Crontab
```
* * * * *    runner.sh       # Crawler cron
*/5 * * * *  watchdog.sh     # Health check
@reboot      linkedin_worker.py  # Redis worker
```

---

## 5. Presentaciones (`!make-ppt`)

### Cómo funciona (LLM → create.js → PptxGenJS)

```
!make-ppt --context norgine --palette pharma 10 slides para VP IT
  → Lee contexto (norgine.md)
  → LLM (Claude Sonnet) genera un create.js COMPLETO a medida
  → node create.js → .pptx con diseño profesional
  → Envía .pptx como adjunto por WhatsApp/Telegram
```

Cada presentación es **ÚNICA** — el LLM genera código JS diferente cada vez,
adaptado al contenido, audiencia y paleta solicitada.

### Paletas

| Paleta | Colores | Uso ideal |
|---|---|---|
| `pharma` (default) | Navy + Teal + Gold | Pharma, biotech, healthcare |
| `tech` | Negro + Teal + Amber | Tech, startups |
| `bold` | Carbón + Naranja + Sand | Impacto visual, marketing |
| `trust` | Navy + Ice Blue + Teal | Consulting, finanzas |
| `executive` | Negro + Verde GitHub | Developer, ejecutivo C-suite |

### Uso

```
!make-ppt 5 slides sobre AI en payments               → pharma (default)
!make-ppt --palette tech 5 slides sobre fintech        → tech
!make-ppt --context norgine 10 slides para VP IT       → pharma + contexto
!make-ppt --context norgine --palette executive 7 slides → executive + contexto
```

### Diseño obligatorio (en system prompt del LLM)

- Barra lateral izquierda (TEAL + GOLD) en Title/CTA slides
- Header (sección CAPS + título) en slides de contenido
- Footer en TODAS las slides
- Iconos de `react-icons` → PNG base64 via `sharp`
- Cards con sombra (shape offset +0.04)
- Tipografía: título 40-52pt, sección 8-9pt, body 9-11pt
- Nunca texto-only — siempre elemento visual

### Archivos

| Archivo | Función |
|---|---|
| `ops/ppt_dynamic.py` | Motor principal: prompt → LLM → create.js → node → .pptx |
| `ops/ppt_example.js` | Ejemplo gold-standard (referencia para el LLM) |
| `ops/openclaw_skills/make-ppt.sh` | Skill wrapper |
| `ops/package.json` | Deps Node.js (pptxgenjs, react-icons, sharp) |
| `context/` | Archivos .md/.pdf de contexto (drag & drop local) |

---

## 5. Análisis Web (`!analysis`)

### Flujo

```
!analysis https://norgine.com/clinical-trial-disclosure/
  → Scraping de la URL principal (HTML → texto)
  → Extrae links de la página
  → Sigue hasta 10 links (prioriza PDFs y docs, luego mismo dominio)
  → Extrae texto de cada link (HTML, PDF, TXT, CSV, JSON)
  → Agrega todo el contenido (hasta 50k chars)
  → LLM genera análisis estructurado:
    ├── Resumen Ejecutivo
    ├── Hallazgos Clave
    ├── Documentos Analizados
    ├── Análisis Detallado
    ├── Observaciones/Riesgos
    └── Recomendaciones
  → Guarda reporte .md completo
  → Envía resumen por WhatsApp + archivo .md
```

### Formatos soportados

| Formato | Extracción |
|---|---|
| HTML | BeautifulSoup → texto limpio |
| PDF | markitdown / pdfplumber |
| Text/CSV | Directo |
| JSON | Directo |

### Flags

```
!analysis https://example.com                      → Análisis directo
!analysis https://example.com busco ensayos fase 3  → Con contexto inline
!analysis --context https://example.com             → Usa !context guardado
```

### Archivos

| Archivo | Función |
|---|---|
| `ops/web_analyzer.py` | Motor: scraping + crawl + LLM analysis |
| `ops/openclaw_skills/analysis.sh` | Skill wrapper |

---

## 6. Sistema de Contexto (`!context`)

Almacena texto como archivos `.md` persistentes para reutilizar en cualquier comando.

### Guardar

```
!context norgine Norgine es una empresa farmacéutica que se especializa en...
  → Guarda: /context/norgine.md

!context <texto sin nombre>
  → Guarda: /context/default.md
```

### Gestionar

```
!context-list                    → Lista todos los contextos
!context-show norgine            → Ver contenido
!context-clear norgine           → Borrar uno
!context-clear                   → Borrar todos
```

### Usar en comandos

```
!make-ppt --context norgine --template 5 10 slides para VP IT
!analysis --context norgine https://norgine.com/
```

### Resolución inteligente

El flag `--context <nombre>` busca en orden de prioridad:

| # | Ubicación | Ejemplo |
|---|---|---|
| 1 | `~/.openclaw/workspace/context/{name}.md` | `context/norgine.md` |
| 2 | `~/.openclaw/workspace/context/{name}.pdf` | `context/norgine.pdf` |
| 3 | `~/.openclaw/workspace/context/{name}` | `context/norgine` (exacto) |
| 4 | `~/.openclaw/workspace/{name}.md` | `workspace/norgine.md` |
| 5 | `~/.openclaw/workspace/{name}.pdf` | `workspace/norgine.pdf` |
| 6 | `~/.openclaw/workspace/{name}` | `workspace/norgine` (exacto) |

- Soporta **`.md`** y **`.pdf`** (PDF se extrae con markitdown)
- Se puede pasar con o sin extensión: `--context norgine` = `--context norgine.md`
- **Persistente** — sin TTL, los archivos se quedan hasta que los borres

---

## 7. Sistema de Facturas

### Flujo `!make-invoice`

```
"!make-invoice 5000 consulting para TechCorp"
  → LLM parsea la solicitud (monto, concepto, cliente)
  → Busca cliente en DB local (data/clients.json)
    → Si no existe: LLM busca datos fiscales → guarda en DB
  → Genera número secuencial (OC-FRA003, OC-FRA004...)
  → Jinja2 + WeasyPrint → PDF profesional
  → Responde con resumen + ruta del PDF
```

### Datos del emisor (hardcoded en template)
- **Nombre**: Alberto Jesús Lebrón Lobo
- **CIF**: 09038288-R
- **Dirección**: C/ Taulat 60, 08005 Barcelona
- **Impuestos**: IVA 21% + IRPF 15%

---

## 8. ICS Email Watcher

Servicio automático que monitorea el inbox de `dealflow@nexusfinlabs.com` cada **1 minuto**.

```
Email con .ics → IMAP poll → Extrae ICS → Google Calendar API → WhatsApp notification
```

---

## 9. Docker Stack

| Container | Puerto | Función |
|---|---|---|
| `oc_postgres` | interno | Base de datos principal |
| `oc_redis` | interno | Cola de trabajos + contexto |
| `oc_api` | 8000 | Crawler API + Document Generator |
| `oc_worker` | — | Procesador asíncrono |
| `oc_exporter` | 8001 | Google Sheets export |

---

## 10. APIs y Credenciales

| API | Uso | Env var |
|---|---|---|
| OpenRouter | LLM (GPT-4o-mini) | `OPENROUTER_API_KEY` |
| Hunter.io | Email discovery | `HUNTER_API_KEY` |
| Snov.io | Email discovery | `SNOVIO_CLIENT_ID` + `SNOVIO_CLIENT_SECRET` |
| ZeroBounce | Email validation | `ZEROBOUNCE_API_KEY` |
| SerpAPI | Google/LinkedIn search | `SERPAPI_KEY` |
| Google Calendar | ICS → Calendar | `GOOGLE_APPLICATION_CREDENTIALS` |
| Google Sheets | LinkedIn → Sheets | `GOOGLE_APPLICATION_CREDENTIALS` |
| IMAP/SMTP | Email (IONOS) | `EMAIL_PASSWORD` |
| Redis | Contexto + jobs | `REDIS_URL` |

Todas en `~/openclawd_stack/.env` (nunca en git).

---

## 11. Deployment

```bash
# Deploy automatizado (desde local)
cd ~/Desktop/SW_AI/openclawd-vps/project && bash deploy.sh

# Manual (rsync + restart)
rsync -av --exclude '.env' --exclude 'node_modules' openclawd_stack/ openclawd-vps:~/openclawd_stack/
ssh openclawd-vps "kill $(pgrep -f command_router.py); cd ~/openclawd_stack && nohup python3 ops/command_router.py >> /tmp/command_router.log 2>&1 &"
```

---

## 12. Flujos Productivos — Propuestos 🆕

| Flujo | Descripción | Complejidad | Prioridad |
|---|---|---|---|
| 🔄 `!follow-up` | Detecta emails sin respuesta en 48h → draft follow-up | Media | ⭐⭐⭐ |
| 📋 `!pipeline [tab]` | View/update CRM pipeline en Google Sheets | Baja | ⭐⭐⭐ |
| 🧠 `!research <empresa>` | Análisis completo de empresa: web + LinkedIn + financials | Alta | ⭐⭐⭐ |
| 📊 `!report <tab> [period]` | Genera reporte ejecutivo de actividad (LinkedIn, emails, deals) | Media | ⭐⭐ |
| 🌍 `!translate <lang> <doc>` | Traduce documentos/emails manteniendo formato | Baja | ⭐⭐ |
| 📝 `!summarize <url/doc>` | Resumen ejecutivo rápido (sin crawl profundo, más rápido que !analysis) | Baja | ⭐⭐ |
| 🔔 `!monitor <url> [interval]` | Monitorea cambios en una web (hash cada Nh, notifica cambios) | Media | ⭐ |
| 📧 `!outreach-blast <tab> <template>` | Envío masivo personalizado desde Sheets | Alta | ⭐ |
| 🗂️ `!archive <doc>` | Guarda documento en estructura organizada + índice | Baja | ⭐ |

### Detalle de los más interesantes:

**`!follow-up`** — Cron diario. Escanea IMAP sent folder. Si un email enviado hace >48h no tiene respuesta, genera un draft follow-up personalizado con LLM. Envía notificación: "3 follow-ups pendientes, ¿los envío?"

**`!research <empresa>`** — Combina: web scraping (sitio corporativo), LinkedIn search (C-suite), datos financieros (si public), y genera un dossier ejecutivo. Ideal para preparar reuniones de M&A.

**`!pipeline [update]`** — Lee/escribe un tab "Pipeline" en Google Sheets. Commands: `!pipeline` (ver resumen), `!pipeline add TechCorp 500k qualify`, `!pipeline move TechCorp closing`.

**`!report weekly`** — Agrega métricas de la semana: emails enviados, LinkedIn profiles encontrados, facturas generadas, propuestas enviadas. Genera un mini-dashboard en texto.
