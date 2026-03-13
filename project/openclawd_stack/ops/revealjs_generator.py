#!/usr/bin/env python3
"""
Reveal.js Presentation Generator — Modern HTML presentations.

Usage:
  python3 revealjs_generator.py "5 slides sobre AI en payments"
  python3 revealjs_generator.py --theme dark "10 slides sobre M&A strategy"

Themes: dark (default), light, gradient

Flow:
  1. LLM generates structured slide content (JSON)
  2. Builds self-contained HTML with Reveal.js CDN
  3. Returns path to .html file (can be opened in any browser)
"""

import json
import os
import re
import sys
import requests
import logging
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────
DRAFTS_DIR = "/home/albi_agent/.openclaw/workspace/docs/drafts"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

REVEAL_CDN = "https://cdn.jsdelivr.net/npm/reveal.js@5.1.0"

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("revealjs_generator")


def load_env():
    for path in ["/home/albi_agent/openclawd_stack/.env", ".env"]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k, v.strip("\"'"))
    global OPENROUTER_API_KEY
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")


# ═══════════════════════════════════════════════════════
#  LLM Content Generation
# ═══════════════════════════════════════════════════════

def generate_slide_content(user_prompt):
    """Use LLM to generate structured slide content optimized for Reveal.js."""
    system = """Eres un diseñador de presentaciones web de nivel ejecutivo.
Genera contenido para slides en JSON. Sé conciso, visual y moderno.

Cada slide tiene:
- type: "cover" | "content" | "two_column" | "highlight" | "stats" | "timeline" | "closing"
- title: título principal
- subtitle: (opcional)
- bullets: lista de puntos (max 5, texto corto)
- left_title / left_bullets / right_title / right_bullets: para two_column
- quote: texto destacado (para highlight)
- stats: lista de {"value": "98%", "label": "Adoption rate"} (para stats, max 4)
- timeline: lista de {"year": "2024", "event": "Descripción"} (para timeline)
- icon_hint: emoji relevante
- footer_note: texto inferior (fuente, etc.)
- bg_accent: "blue" | "purple" | "green" | "orange" (color de acento para esta slide)

Instrucciones:
- La primera slide SIEMPRE es "cover"
- La última slide SIEMPRE es "closing"
- Varía los tipos para una presentación dinámica
- Usa "stats" para datos cuantitativos
- Usa "highlight" para frases impactantes
- Usa "timeline" para secuencias temporales

Responde SOLO con un JSON array válido."""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
            },
            timeout=30,
        )
        content = resp.json()["choices"][0]["message"]["content"]
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        log.error("LLM slide generation failed: %s", e)
    return None


# ═══════════════════════════════════════════════════════
#  Slide Renderers (HTML fragments)
# ═══════════════════════════════════════════════════════

def _esc(text):
    """Escape HTML."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _accent_color(data):
    """Get accent color for a slide."""
    accent_map = {
        "blue": "#38BDF8",
        "purple": "#818CF8",
        "green": "#4ADE80",
        "orange": "#FBBF24",
        "cyan": "#22D3EE",
        "pink": "#F472B6",
    }
    return accent_map.get(data.get("bg_accent", ""), "#38BDF8")


def render_cover(data):
    icon = _esc(data.get("icon_hint", "🚀"))
    accent = _accent_color(data)
    return f"""<section data-background-color="#0B0F1A">
  <div class="cover-slide">
    <div class="cover-icon">{icon}</div>
    <div class="cover-bar" style="background: {accent};"></div>
    <h1 class="cover-title">{_esc(data.get('title', ''))}</h1>
    <p class="cover-subtitle">{_esc(data.get('subtitle', ''))}</p>
    <div class="cover-footer">
      <span>Alberto Lebrón · Nexus FinLabs</span>
      <span>{datetime.now().strftime('%B %Y')}</span>
    </div>
  </div>
  <div class="cover-orb" style="background: radial-gradient(circle, {accent}33, transparent);"></div>
</section>"""


def render_content(data, num):
    icon = _esc(data.get("icon_hint", ""))
    accent = _accent_color(data)
    bullets_html = ""
    for i, b in enumerate(data.get("bullets", [])[:6]):
        delay = i * 100
        bullets_html += f"""
    <div class="bullet-item fragment fade-up" data-fragment-index="{i}" style="animation-delay: {delay}ms">
      <div class="bullet-bar" style="background: {accent};"></div>
      <span>{_esc(b)}</span>
    </div>"""

    footer = ""
    if data.get("footer_note"):
        footer = f'<div class="slide-footer">{_esc(data["footer_note"])}</div>'

    return f"""<section data-background-color="#0B0F1A">
  <div class="content-slide">
    <div class="slide-header">
      <span class="slide-num" style="background: {accent};">{num:02d}</span>
      <h2>{icon} {_esc(data.get('title', ''))}</h2>
    </div>
    <div class="accent-line" style="background: {accent};"></div>
    <div class="bullets-container">{bullets_html}
    </div>
    {footer}
  </div>
</section>"""


def render_two_column(data):
    accent = _accent_color(data)
    icon = _esc(data.get("icon_hint", ""))

    left_items = "".join(
        f'<li class="fragment fade-right">{_esc(b)}</li>'
        for b in data.get("left_bullets", [])[:4]
    )
    right_items = "".join(
        f'<li class="fragment fade-left">{_esc(b)}</li>'
        for b in data.get("right_bullets", [])[:4]
    )

    return f"""<section data-background-color="#0B0F1A">
  <div class="content-slide">
    <h2>{icon} {_esc(data.get('title', ''))}</h2>
    <div class="accent-line" style="background: {accent};"></div>
    <div class="two-columns">
      <div class="column-card">
        <h3 style="color: {accent};">{_esc(data.get('left_title', ''))}</h3>
        <ul>{left_items}</ul>
      </div>
      <div class="column-card">
        <h3 style="color: #818CF8;">{_esc(data.get('right_title', ''))}</h3>
        <ul>{right_items}</ul>
      </div>
    </div>
  </div>
</section>"""


def render_highlight(data):
    accent = _accent_color(data)
    footer = ""
    if data.get("footer_note"):
        footer = f'<p class="highlight-source">{_esc(data["footer_note"])}</p>'

    return f"""<section data-background-color="#0B0F1A">
  <div class="highlight-slide">
    <div class="highlight-card" style="border-color: {accent};">
      <div class="quote-mark" style="color: {accent};">❝</div>
      <p class="highlight-text fragment fade-up">{_esc(data.get('quote', data.get('title', '')))}</p>
      {footer}
    </div>
  </div>
</section>"""


def render_stats(data):
    accent = _accent_color(data)
    stats = data.get("stats", [])[:4]
    cards = ""
    for i, s in enumerate(stats):
        color = ["#38BDF8", "#818CF8", "#4ADE80", "#FBBF24"][i % 4]
        cards += f"""
      <div class="stat-card fragment zoom-in" data-fragment-index="{i}">
        <div class="stat-value" style="color: {color};">{_esc(s.get('value', ''))}</div>
        <div class="stat-label">{_esc(s.get('label', ''))}</div>
      </div>"""

    icon = _esc(data.get("icon_hint", "📊"))
    return f"""<section data-background-color="#0B0F1A">
  <div class="content-slide">
    <h2>{icon} {_esc(data.get('title', ''))}</h2>
    <div class="accent-line" style="background: {accent};"></div>
    <div class="stats-grid">{cards}
    </div>
  </div>
</section>"""


def render_timeline(data):
    accent = _accent_color(data)
    icon = _esc(data.get("icon_hint", "📅"))
    events = data.get("timeline", [])[:5]
    items = ""
    for i, ev in enumerate(events):
        items += f"""
      <div class="timeline-item fragment fade-up" data-fragment-index="{i}">
        <div class="timeline-dot" style="background: {accent};"></div>
        <div class="timeline-content">
          <span class="timeline-year" style="color: {accent};">{_esc(ev.get('year', ''))}</span>
          <span class="timeline-event">{_esc(ev.get('event', ''))}</span>
        </div>
      </div>"""

    return f"""<section data-background-color="#0B0F1A">
  <div class="content-slide">
    <h2>{icon} {_esc(data.get('title', ''))}</h2>
    <div class="accent-line" style="background: {accent};"></div>
    <div class="timeline">{items}
    </div>
  </div>
</section>"""


def render_closing(data):
    accent = _accent_color(data)
    return f"""<section data-background-color="#0B0F1A">
  <div class="closing-slide">
    <div class="closing-orb" style="background: radial-gradient(circle, {accent}22, transparent);"></div>
    <h1 class="closing-title fragment fade-up">{_esc(data.get('title', 'Gracias'))}</h1>
    <p class="closing-subtitle fragment fade-up" style="color: {accent};">{_esc(data.get('subtitle', ''))}</p>
    <div class="closing-contact fragment fade-up">
      <span>dealflow@nexusfinlabs.com</span>
      <span>·</span>
      <span>+34 605 693 177</span>
    </div>
  </div>
</section>"""


# ═══════════════════════════════════════════════════════
#  Full HTML Assembly
# ═══════════════════════════════════════════════════════

STYLES = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

:root {
  --bg-dark: #0B0F1A;
  --bg-card: #131A2E;
  --primary: #38BDF8;
  --secondary: #818CF8;
  --accent-green: #4ADE80;
  --accent-warm: #FBBF24;
  --text: #E2E8F0;
  --text-muted: #64748B;
  --divider: #1E293B;
}

.reveal { font-family: 'Inter', sans-serif; }
.reveal h1, .reveal h2, .reveal h3 { font-family: 'Inter', sans-serif; font-weight: 700; }

/* Cover */
.cover-slide { position: relative; text-align: left; padding: 40px 60px; z-index: 2; }
.cover-icon { font-size: 3em; margin-bottom: 10px; }
.cover-bar { width: 80px; height: 4px; border-radius: 2px; margin: 10px 0 20px; }
.cover-title { font-size: 2.6em !important; font-weight: 800 !important; color: white !important;
  line-height: 1.15 !important; margin: 0 !important; max-width: 80%; }
.cover-subtitle { font-size: 1.2em; color: var(--text); opacity: 0.7; margin-top: 20px; font-weight: 300; }
.cover-footer { position: absolute; bottom: 40px; left: 60px; right: 60px;
  display: flex; justify-content: space-between; font-size: 0.7em; color: var(--text-muted); }
.cover-orb { position: absolute; top: -100px; right: -100px; width: 500px; height: 500px;
  border-radius: 50%; z-index: 1; filter: blur(60px); opacity: 0.5; }

/* Content slides */
.content-slide { text-align: left; padding: 20px 50px; }
.slide-header { display: flex; align-items: center; gap: 15px; margin-bottom: 5px; }
.slide-header h2 { font-size: 1.6em !important; color: white !important; margin: 0 !important; }
.slide-num { display: inline-flex; align-items: center; justify-content: center;
  width: 36px; height: 28px; border-radius: 6px; font-size: 0.8em;
  font-weight: 700; color: var(--bg-dark); flex-shrink: 0; }
.accent-line { width: 80px; height: 3px; border-radius: 2px; margin: 12px 0 25px; }

/* Bullets */
.bullets-container { display: flex; flex-direction: column; gap: 14px; }
.bullet-item { display: flex; align-items: flex-start; gap: 14px; font-size: 0.88em;
  color: var(--text); line-height: 1.5; }
.bullet-bar { width: 4px; min-height: 28px; border-radius: 2px; flex-shrink: 0; margin-top: 3px; }
.slide-footer { position: absolute; bottom: 30px; left: 50px; font-size: 0.6em; color: var(--text-muted); }

/* Two columns */
.two-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-top: 20px; }
.column-card { background: var(--bg-card); border-radius: 12px; padding: 25px 30px; }
.column-card h3 { font-size: 1em !important; margin: 0 0 15px 0 !important; font-weight: 600; }
.column-card ul { list-style: none; padding: 0; margin: 0; }
.column-card li { color: var(--text); font-size: 0.82em; padding: 8px 0;
  border-bottom: 1px solid var(--divider); line-height: 1.4; }
.column-card li:last-child { border-bottom: none; }

/* Highlight */
.highlight-slide { display: flex; align-items: center; justify-content: center; height: 100%; }
.highlight-card { background: var(--bg-card); border-radius: 16px; padding: 50px 60px;
  max-width: 750px; text-align: center; border-left: 4px solid; }
.quote-mark { font-size: 2.5em; line-height: 1; margin-bottom: 10px; }
.highlight-text { font-size: 1.5em !important; color: white !important; font-weight: 600;
  line-height: 1.4 !important; margin: 0 !important; }
.highlight-source { font-size: 0.7em; color: var(--text-muted); margin-top: 20px; }

/* Stats */
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 20px; margin-top: 25px; }
.stat-card { background: var(--bg-card); border-radius: 12px; padding: 30px;
  text-align: center; transition: transform 0.3s ease; }
.stat-card:hover { transform: translateY(-4px); }
.stat-value { font-size: 2.4em; font-weight: 800; line-height: 1.2; }
.stat-label { font-size: 0.75em; color: var(--text-muted); margin-top: 8px; text-transform: uppercase;
  letter-spacing: 0.05em; }

/* Timeline */
.timeline { display: flex; flex-direction: column; gap: 20px; margin-top: 20px; padding-left: 20px;
  border-left: 2px solid var(--divider); }
.timeline-item { display: flex; align-items: flex-start; gap: 15px; position: relative; }
.timeline-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; margin-top: 5px;
  margin-left: -26px; }
.timeline-content { display: flex; flex-direction: column; gap: 2px; }
.timeline-year { font-weight: 700; font-size: 0.9em; }
.timeline-event { font-size: 0.82em; color: var(--text); line-height: 1.4; }

/* Closing */
.closing-slide { display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; position: relative; }
.closing-orb { position: absolute; width: 400px; height: 400px; border-radius: 50%;
  filter: blur(80px); opacity: 0.4; }
.closing-title { font-size: 2.8em !important; color: white !important; margin: 0 !important;
  font-weight: 800 !important; z-index: 2; }
.closing-subtitle { font-size: 1.1em; margin-top: 15px !important; font-weight: 400; z-index: 2; }
.closing-contact { display: flex; gap: 10px; font-size: 0.75em; color: var(--text-muted);
  margin-top: 40px; z-index: 2; }

/* Animations */
.fragment.fade-up { transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1) !important; }
.fragment.zoom-in { transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important; }
"""


def build_html(slides_data, title="Presentación"):
    """Build complete self-contained Reveal.js HTML."""
    slides_html = ""
    slide_num = 0

    for sdata in slides_data:
        stype = sdata.get("type", "content")
        if stype == "cover":
            slides_html += render_cover(sdata)
        elif stype == "closing":
            slides_html += render_closing(sdata)
        elif stype == "two_column":
            slides_html += render_two_column(sdata)
        elif stype == "highlight":
            slides_html += render_highlight(sdata)
        elif stype == "stats":
            slides_html += render_stats(sdata)
        elif stype == "timeline":
            slides_html += render_timeline(sdata)
        else:
            slide_num += 1
            slides_html += render_content(sdata, slide_num)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_esc(title)}</title>
  <link rel="stylesheet" href="{REVEAL_CDN}/dist/reveal.css">
  <link rel="stylesheet" href="{REVEAL_CDN}/dist/theme/black.css">
  <style>{STYLES}</style>
</head>
<body>
  <div class="reveal">
    <div class="slides">
{slides_html}
    </div>
  </div>
  <script src="{REVEAL_CDN}/dist/reveal.js"></script>
  <script>
    Reveal.initialize({{
      hash: true,
      transition: 'slide',
      transitionSpeed: 'default',
      backgroundTransition: 'fade',
      controls: true,
      progress: true,
      center: false,
      width: 1280,
      height: 720,
    }});
  </script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════
#  Main Generator
# ═══════════════════════════════════════════════════════

def generate_revealjs(user_prompt):
    """Main function: LLM content → Reveal.js HTML."""
    load_env()
    log.info("Generating Reveal.js for: %s", user_prompt[:80])

    slides_data = generate_slide_content(user_prompt)
    if not slides_data:
        return None, "❌ LLM no pudo generar el contenido de las slides"

    log.info("LLM generated %d slides", len(slides_data))

    # Extract title from cover slide
    title = "Presentación"
    for s in slides_data:
        if s.get("type") == "cover":
            title = s.get("title", title)
            break

    html = build_html(slides_data, title=title)

    # Save
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', user_prompt[:30]).strip('_')
    filename = f"PPT_{safe_name}_{timestamp}.html"
    filepath = os.path.join(DRAFTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    log.info("Reveal.js saved: %s", filepath)

    summary = (
        f"🎨 *Presentación Reveal.js generada*\n\n"
        f"📁 Archivo: `{filename}`\n"
        f"📄 Slides: {len(slides_data)}\n"
        f"🌐 Formato: HTML (abrir en navegador)\n"
        f"📎 Ruta: {filepath}\n"
        f"\n💡 _Abre el archivo en Chrome/Firefox para ver las animaciones._"
    )

    return filepath, summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reveal.js Presentation Generator")
    parser.add_argument("prompt", nargs="*", help="Descripción de la presentación")
    parser.add_argument("--prompt-file", default=None, help="Read prompt from file (for large context)")
    args = parser.parse_args()

    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    elif args.prompt:
        prompt = " ".join(args.prompt)
    else:
        print('Usage: python3 revealjs_generator.py "descripción" or --prompt-file /path')
        sys.exit(1)

    filepath, message = generate_revealjs(prompt)
    print(message)
