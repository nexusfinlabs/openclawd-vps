#!/usr/bin/env python3
"""
ppt_dynamic.py — LLM-powered PptxGenJS presentation generator.

Flow:
  1. Reads prompt (+ optional context)
  2. Calls Anthropic API DIRECT with expert PptxGenJS system prompt
  3. LLM returns a complete create.js
  4. Executes: node create.js → output.pptx
  5. Returns the path to the generated .pptx

Usage:
  python3 ppt_dynamic.py --prompt-file /tmp/prompt.txt [--palette pharma]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time

# ── API Config ──
# Use Anthropic DIRECT (not OpenRouter)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"

DRAFTS_DIR = "/home/albi_agent/.openclaw/workspace"

PALETTES = {
    "pharma": {
        "desc": "Navy + Teal + Gold (pharma/biotech)",
        "NAVY": "0A1628", "DARK": "0F2040", "TEAL": "00A896", "GOLD": "F0C040",
        "ICE": "C8E6E3", "WHITE": "FFFFFF", "MUTED": "7A9BB5",
        "CARD": "132238", "LIGHT": "F0F6FA", "BORDER": "1A3A5C",
    },
    "tech": {
        "desc": "Negro + Teal + Amber (tech/startup)",
        "NAVY": "0F1923", "DARK": "0A1117", "TEAL": "02C39A", "GOLD": "F59E0B",
        "ICE": "B8D4CE", "WHITE": "FFFFFF", "MUTED": "8899AA",
        "CARD": "1A2535", "LIGHT": "F0F4F8", "BORDER": "1E3348",
    },
    "bold": {
        "desc": "Carbón + Naranja + Sand",
        "NAVY": "1E2022", "DARK": "151718", "TEAL": "2A9D8F", "GOLD": "E85D26",
        "ICE": "F5EFE6", "WHITE": "FFFFFF", "MUTED": "9A9A9A",
        "CARD": "2A2C2E", "LIGHT": "FAF8F5", "BORDER": "3A3C3E",
    },
    "trust": {
        "desc": "Navy + Ice Blue + Teal",
        "NAVY": "1E2761", "DARK": "161D4A", "TEAL": "028090", "GOLD": "E8B931",
        "ICE": "CADCFC", "WHITE": "FFFFFF", "MUTED": "7A8BA5",
        "CARD": "242D6B", "LIGHT": "F0F2FA", "BORDER": "2E3878",
    },
    "executive": {
        "desc": "Negro + Verde GitHub (developer/exec)",
        "NAVY": "0D1117", "DARK": "010409", "TEAL": "238636", "GOLD": "F78166",
        "ICE": "C9D1D9", "WHITE": "FFFFFF", "MUTED": "8B949E",
        "CARD": "161B22", "LIGHT": "F0F2F5", "BORDER": "21262D",
    },
}

EXAMPLE_PATH = os.path.join(os.path.dirname(__file__), "ppt_example.js")

SYSTEM_PROMPT = r"""Eres un experto en crear presentaciones PowerPoint profesionales con pptxgenjs.

Cuando el usuario te pase instrucciones, generas un create.js completo y ejecutable.

REGLAS TÉCNICAS OBLIGATORIAS:
- Layout siempre LAYOUT_16x9 (10" x 5.625")
- Todo el código dentro de async function main()
- La primera línea SIEMPRE: const pptxgen = require("pptxgenjs");
- Imports de react, react-dom/server, sharp y react-icons SIEMPRE incluidos
- Helper ico() para convertir react-icons a PNG base64 SIEMPRE incluido
- Colores sin # (ej: "1B2B5E" no "#1B2B5E")
- shadow con opacity separado, nunca en hex
- margin: 0 en textos alineados con shapes
- Bullets con { bullet: true }, nunca "• " unicode
- Guardar con: await pres.writeFile({ fileName: "OUTPUT_FILENAME" })
- Sin markdown, sin explicaciones — solo código JS puro ejecutable
- NUNCA uses require("fs") ni leas archivos — todo inline en el JS

ANTI-PATRÓN PROHIBIDO — SLIDES EN BLANCO:
❌ NUNCA hagas esto:
  const s = pres.addSlide();
  s.addText("Title", {x:1, y:1, w:8, h:1, fontSize:24});
Eso genera slides BLANCAS sin diseño.

✅ SIEMPRE haz esto:
  const s = pres.addSlide();
  s.background = { color: C.NAVY };  // ← OBLIGATORIO
  s.addShape("rect", {x:0, y:0, w:10, h:0.82, fill:{color:C.NAVY}});  // header
  s.addShape("rect", {x:0, y:0.82, w:10, h:0.045, fill:{color:C.TEAL}});  // accent
  // ... contenido con shapes, cards, badges ...
  s.addShape("rect", {x:0, y:5.325, w:10, h:0.3, fill:{color:"061020"}});  // footer

ESTRUCTURA OBLIGATORIA DE CADA SLIDE:
1. s.background = { color: C.NAVY }  ← SIEMPRE primer paso
2. Header shape (rect w:10 h:0.82)
3. Accent bar (rect h:0.045)
4. Contenido con SHAPES (cards, rects, ellipses) — NUNCA solo texto
5. Footer shape (rect y:5.325 h:0.3)

HELPER ico() OBLIGATORIO (copiar tal cual):
```
async function ico(IconComponent, color = "FFFFFF", size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color: `#${color}`, size: String(size) })
  );
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
```

HELPERS addFooter() y addHeader() OBLIGATORIOS — definirlos y usarlos en TODAS las slides.

TIPOS DE SLIDES (adaptar al nº que pida el usuario):
1. Title slide — fondo NAVY, barra lateral (TEAL + GOLD), título 50pt, chips, ellipses decorativos
2. Métricas — 3 cards con número grande (72pt), icono, accent bar superior
3. Tabla visual — rows alternantes con badges de color
4. Split — dos paneles side-by-side
5. Cards — 3-4 cards verticales con sombra offset +0.04
6. Proceso — filas numeradas con badge de color + icono
7. CTA — fondo NAVY, barra lateral, título 52pt, pasos con círculos

DISEÑO OBLIGATORIO:
- Barra lateral (0.5" TEAL + 0.04" GOLD) en Title y CTA
- Cards con sombra: rect offset +0.04, transparency 60
- Tipografía: título 40-52pt, sección 8-9pt CAPS charSpacing 3, body 9-11pt
- fontFace siempre "Calibri"
- NUNCA texto-only — SIEMPRE shapes debajo

RESPONDE ÚNICAMENTE CON EL CÓDIGO JS. Nada de texto ni explicaciones."""


def _load_example() -> str:
    if os.path.exists(EXAMPLE_PATH):
        with open(EXAMPLE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def call_llm(prompt: str, palette_name: str, output_filename: str) -> str:
    """Call Anthropic API directly to generate create.js code."""
    import requests

    palette = PALETTES.get(palette_name, PALETTES["pharma"])
    palette_code = "\n".join(f'  {k}: "{v}",' for k, v in palette.items() if k != "desc")

    example = _load_example()
    example_block = ""
    if example:
        example_block = f"""

EJEMPLO DE REFERENCIA (calidad que debes igualar o superar):
<example>
{example}
</example>

Genera código al MISMO nivel de detalle visual. No copies el contenido,
genera contenido NUEVO pero con la misma calidad visual."""

    user_message = f"""Genera un create.js completo usando esta paleta:

const C = {{
{palette_code}
}};

NOMBRE DEL ARCHIVO DE SALIDA: "{output_filename}"
{example_block}

INSTRUCCIONES DEL USUARIO:
{prompt}
"""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "max_tokens": 16000,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_message},
        ],
    }

    print(f"🎨 Generando con paleta '{palette_name}' ({palette.get('desc', '')})...")
    print(f"  → Anthropic API ({MODEL})...")

    resp = requests.post(ANTHROPIC_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    content = data["content"][0]["text"]

    # Extract JS code — strip markdown fences if present
    code = content.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)

    return code


def main():
    parser = argparse.ArgumentParser(description="LLM-powered PptxGenJS generator")
    parser.add_argument("--prompt-file", required=True, help="Path to prompt text file")
    parser.add_argument("--palette", default="pharma", help="Color palette name")
    args = parser.parse_args()

    with open(args.prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read().strip()

    if not prompt:
        print("❌ Prompt vacío")
        sys.exit(1)

    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY no configurada en .env")
        sys.exit(1)

    # Generate output filename
    slug = re.sub(r"[^a-z0-9]+", "_", prompt[:40].lower()).strip("_")
    timestamp = int(time.time())
    output_filename = f"PPT_{slug}_{timestamp}.pptx"
    output_path = os.path.join(DRAFTS_DIR, output_filename)

    # Call LLM to generate create.js
    try:
        js_code = call_llm(prompt, args.palette, output_filename)
    except Exception as e:
        print(f"❌ Error llamando al LLM: {e}")
        sys.exit(1)

    # Write create.js to temp dir
    work_dir = tempfile.mkdtemp(prefix="ppt_")
    create_js_path = os.path.join(work_dir, "create.js")

    with open(create_js_path, "w", encoding="utf-8") as f:
        f.write(js_code)

    print(f"📝 create.js generado ({len(js_code):,} chars)")

    # Execute: node create.js
    node_path = "/home/albi_agent/.nvm/versions/node/v22.22.0/bin/node"
    node_modules = "/home/albi_agent/openclawd_stack/ops/node_modules"

    env = os.environ.copy()
    env["NODE_PATH"] = node_modules

    try:
        result = subprocess.run(
            [node_path, create_js_path],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=work_dir,
            env=env,
        )

        if result.returncode != 0:
            print(f"❌ Error ejecutando create.js:\n{result.stderr[:500]}")
            debug_path = os.path.join(DRAFTS_DIR, f"debug_create_{timestamp}.js")
            with open(debug_path, "w") as f:
                f.write(js_code)
            print(f"🔍 JS guardado para debug: {debug_path}")
            sys.exit(1)

        if result.stdout.strip():
            print(result.stdout.strip())

    except subprocess.TimeoutExpired:
        print("❌ Timeout ejecutando create.js (60s)")
        sys.exit(1)

    # Find the generated .pptx
    import shutil
    generated_path = os.path.join(work_dir, output_filename)
    if os.path.exists(generated_path):
        shutil.move(generated_path, output_path)
    else:
        for f in os.listdir(work_dir):
            if f.endswith(".pptx"):
                shutil.move(os.path.join(work_dir, f), output_path)
                break
        else:
            print(f"❌ No se encontró archivo .pptx en {work_dir}")
            print(f"Archivos: {os.listdir(work_dir)}")
            sys.exit(1)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"✅ Presentación generada: {output_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
