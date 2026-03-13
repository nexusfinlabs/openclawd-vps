#!/usr/bin/env python3
"""
PPT Generator — Create professional presentations from natural language.

Usage:
  python3 ppt_generator.py "5 slides sobre AI en payments: tendencias, riesgos, oportunidades"

Flow:
  1. LLM generates structured slide content (JSON)
  2. python-pptx builds .pptx with professional styling
  3. Returns path to generated file
"""

import json
import os
import re
import sys
import requests
import logging
from datetime import datetime
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ── Config ──────────────────────────────────────────────
DRAFTS_DIR = "/home/albi_agent/.openclaw/workspace/docs/drafts"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# ── Color Palette ───────────────────────────────────────
COLORS = {
    "bg_dark": RGBColor(0x0F, 0x17, 0x2A),       # Deep navy
    "bg_accent": RGBColor(0x1A, 0x25, 0x3C),      # Slightly lighter navy
    "primary": RGBColor(0x38, 0xBD, 0xF8),         # Bright cyan
    "secondary": RGBColor(0x81, 0x8C, 0xF8),       # Soft purple
    "accent": RGBColor(0x4A, 0xDE, 0x80),           # Green accent
    "white": RGBColor(0xFF, 0xFF, 0xFF),
    "light_gray": RGBColor(0xA0, 0xAE, 0xC0),
    "text_muted": RGBColor(0x6B, 0x7B, 0x93),
    "gradient_start": RGBColor(0x38, 0xBD, 0xF8),
    "gradient_end": RGBColor(0x81, 0x8C, 0xF8),
}

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("ppt_generator")


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


def generate_slide_content(user_prompt):
    """Use LLM to generate structured slide content."""
    system = """Eres un diseñador de presentaciones profesionales. 
Genera contenido para slides en JSON.
Cada slide tiene: title, subtitle (opcional), bullets (lista de puntos, max 5), 
footer_note (opcional, texto corto inferior).
La primera slide es siempre de portada (type: "cover") con title y subtitle.
La última slide es de cierre (type: "closing") con un mensaje final.
Las demás son de contenido (type: "content").

Responde SOLO con un JSON array válido. Ejemplo:
[
  {"type": "cover", "title": "AI en Payments", "subtitle": "Tendencias 2026"},
  {"type": "content", "title": "Tendencias Clave", "bullets": ["punto 1", "punto 2", "punto 3"]},
  {"type": "content", "title": "Riesgos", "bullets": ["punto 1", "punto 2"], "footer_note": "Fuente: McKinsey 2026"},
  {"type": "closing", "title": "¿Siguiente Paso?", "subtitle": "contacto@empresa.com"}
]"""

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
        # Extract JSON array
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        log.error("LLM slide generation failed: %s", e)

    return None


def _set_slide_background(slide, color):
    """Set solid background color for a slide."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_accent_bar(slide, x, y, width, height, color):
    """Add a colored accent bar/shape."""
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()  # No border


def _add_text_box(slide, text, x, y, width, height, font_size=18,
                  color=None, bold=False, alignment=PP_ALIGN.LEFT, font_name="Calibri"):
    """Add a styled text box to a slide."""
    if color is None:
        color = COLORS["white"]
    txBox = slide.shapes.add_textbox(x, y, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = alignment
    return txBox


def build_cover_slide(prs, slide_data):
    """Build a visually striking title slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
    _set_slide_background(slide, COLORS["bg_dark"])

    # Top accent bar
    _add_accent_bar(slide, Inches(0), Inches(0), Inches(10), Inches(0.06), COLORS["primary"])

    # Left accent line
    _add_accent_bar(slide, Inches(0.8), Inches(2.5), Inches(0.8), Inches(0.05), COLORS["primary"])

    # Title
    _add_text_box(slide, slide_data.get("title", "Presentación"),
                  Inches(0.8), Inches(2.7), Inches(8.4), Inches(1.5),
                  font_size=40, color=COLORS["white"], bold=True)

    # Subtitle
    if slide_data.get("subtitle"):
        _add_text_box(slide, slide_data["subtitle"],
                      Inches(0.8), Inches(4.2), Inches(8.4), Inches(0.8),
                      font_size=20, color=COLORS["light_gray"])

    # Bottom branding
    _add_text_box(slide, "Alberto Lebrón · Nexus FinLabs",
                  Inches(0.8), Inches(6.5), Inches(4), Inches(0.4),
                  font_size=11, color=COLORS["text_muted"])

    # Date
    _add_text_box(slide, datetime.now().strftime("%B %Y"),
                  Inches(7), Inches(6.5), Inches(2.5), Inches(0.4),
                  font_size=11, color=COLORS["text_muted"], alignment=PP_ALIGN.RIGHT)

    # Decorative circle (top right)
    circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(8.2), Inches(0.4), Inches(1.2), Inches(1.2))
    circle.fill.solid()
    circle.fill.fore_color.rgb = COLORS["primary"]
    circle.fill.fore_color.brightness = 0.7
    circle.line.fill.background()


def build_content_slide(prs, slide_data, slide_num):
    """Build a content slide with bullets."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_slide_background(slide, COLORS["bg_dark"])

    # Top bar
    _add_accent_bar(slide, Inches(0), Inches(0), Inches(10), Inches(0.04), COLORS["primary"])

    # Slide number badge
    num_shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5), Inches(0.3), Inches(0.5), Inches(0.4))
    num_shape.fill.solid()
    num_shape.fill.fore_color.rgb = COLORS["primary"]
    num_shape.line.fill.background()
    tf = num_shape.text_frame
    tf.text = f"{slide_num:02d}"
    tf.paragraphs[0].font.size = Pt(12)
    tf.paragraphs[0].font.color.rgb = COLORS["bg_dark"]
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER

    # Title
    _add_text_box(slide, slide_data.get("title", ""),
                  Inches(1.2), Inches(0.3), Inches(8), Inches(0.6),
                  font_size=28, color=COLORS["white"], bold=True)

    # Accent line under title
    _add_accent_bar(slide, Inches(1.2), Inches(1.05), Inches(1), Inches(0.04), COLORS["primary"])

    # Bullets
    bullets = slide_data.get("bullets", [])
    y_start = 1.4
    for i, bullet in enumerate(bullets[:6]):
        # Bullet dot
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.2), Inches(y_start + i * 0.85 + 0.08), Inches(0.12), Inches(0.12))
        dot.fill.solid()
        dot.fill.fore_color.rgb = COLORS["primary"] if i % 2 == 0 else COLORS["secondary"]
        dot.line.fill.background()

        # Bullet text
        _add_text_box(slide, bullet,
                      Inches(1.55), Inches(y_start + i * 0.85), Inches(7.5), Inches(0.75),
                      font_size=16, color=COLORS["light_gray"])

    # Footer note
    if slide_data.get("footer_note"):
        _add_text_box(slide, slide_data["footer_note"],
                      Inches(0.8), Inches(6.6), Inches(8.4), Inches(0.3),
                      font_size=9, color=COLORS["text_muted"])


def build_closing_slide(prs, slide_data):
    """Build a closing/thank you slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_slide_background(slide, COLORS["bg_dark"])

    # Top accent
    _add_accent_bar(slide, Inches(0), Inches(0), Inches(10), Inches(0.06), COLORS["secondary"])

    # Large decorative circle
    circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(3.5), Inches(0.5), Inches(3), Inches(3))
    circle.fill.solid()
    circle.fill.fore_color.rgb = COLORS["bg_accent"]
    circle.line.fill.background()

    # Closing message
    _add_text_box(slide, slide_data.get("title", "Gracias"),
                  Inches(1), Inches(2.5), Inches(8), Inches(1.2),
                  font_size=44, color=COLORS["white"], bold=True, alignment=PP_ALIGN.CENTER)

    if slide_data.get("subtitle"):
        _add_text_box(slide, slide_data["subtitle"],
                      Inches(1), Inches(4.0), Inches(8), Inches(0.8),
                      font_size=18, color=COLORS["primary"], alignment=PP_ALIGN.CENTER)

    # Contact footer
    _add_text_box(slide, "dealflow@nexusfinlabs.com · +34 605 693 177",
                  Inches(1), Inches(6.3), Inches(8), Inches(0.4),
                  font_size=12, color=COLORS["text_muted"], alignment=PP_ALIGN.CENTER)

    # Bottom accent
    _add_accent_bar(slide, Inches(0), Inches(7.2), Inches(10), Inches(0.06), COLORS["primary"])


def generate_pptx(user_prompt):
    """Main function: LLM content → python-pptx → .pptx file."""
    load_env()

    log.info("Generating PPT for: %s", user_prompt[:80])

    # 1. Generate content via LLM
    slides_data = generate_slide_content(user_prompt)
    if not slides_data:
        return None, "❌ LLM no pudo generar el contenido de las slides"

    log.info("LLM generated %d slides", len(slides_data))

    # 2. Build presentation
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    slide_num = 0
    for sdata in slides_data:
        stype = sdata.get("type", "content")
        if stype == "cover":
            build_cover_slide(prs, sdata)
        elif stype == "closing":
            build_closing_slide(prs, sdata)
        else:
            slide_num += 1
            build_content_slide(prs, sdata, slide_num)

    # 3. Save
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', user_prompt[:30]).strip('_')
    filename = f"PPT_{safe_name}_{timestamp}.pptx"
    filepath = os.path.join(DRAFTS_DIR, filename)

    prs.save(filepath)
    log.info("PPTX saved: %s", filepath)

    summary = (
        f"📊 *Presentación generada*\n\n"
        f"📁 Archivo: `{filename}`\n"
        f"📄 Slides: {len(slides_data)}\n"
        f"📎 Ruta: {filepath}\n"
    )

    return filepath, summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ppt_generator.py \"descripción de la presentación\"")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    filepath, message = generate_pptx(prompt)
    print(message)
