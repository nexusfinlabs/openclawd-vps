#!/usr/bin/env python3
"""
ppt_dynamic.py — LLM-powered PptxGenJS presentation generator.

Flow:
  1. Reads prompt (+ optional context)
  2. Calls LLM with expert PptxGenJS system prompt + gold-standard example
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
import requests

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "anthropic/claude-sonnet-4"
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

# The gold-standard example is loaded from a file to keep this script manageable.
# If the example file doesn't exist, we use a shorter inline reference.
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

HELPERS addFooter() y addHeader() OBLIGATORIOS:
- addFooter: barra fina en la parte inferior con label
- addHeader: barra superior con sección (CAPS, charSpacing 3) + título

ESTRUCTURA MÍNIMA DE SLIDES (adaptar al contenido):
1. Title slide — fondo oscuro, barra lateral izquierda (TEAL + línea GOLD), supertítulo CAPS, título grande (40-52pt), chips/tags, elementos decorativos (ellipses con alta transparency)
2. Resumen / métricas — 3 cards con número grande, icono, label, accent bar superior
3. Tabla o datos — tabla visual con rows alternantes, badges de color por categoría
4. Split — dos paneles side-by-side comparando áreas
5. Cards — 3-4 cards verticales con icono en círculo, num, título, descripción, sombra offset
6. Proceso / pasos — filas numeradas con badge de color, icono, label, descripción
7. CTA / Next Steps — fondo oscuro, barra lateral, título grande, pasos con círculos numerados

Si el usuario pide más slides (8, 10, 15), añade slides intermedias con más detalle.

DISEÑO OBLIGATORIO EN CADA SLIDE:
- Barra lateral izquierda en Title y CTA slides (0.5" TEAL + 0.04" GOLD)
- Header con sección + título en slides de contenido
- Footer en TODAS las slides
- Iconos de react-icons (FaFlask, FaBrain, FaChartBar, FaDatabase, etc.) convertidos con ico()
- Cards con sombra (rect offset +0.04 con transparency 60)
- Jerarquía tipográfica: título 40-52pt, sección 8-9pt CAPS charSpacing 3, body 9-11pt
- Nunca texto-only, siempre elemento visual (icono, card, shape, badge)
- Uso de circles decorativos con alta transparency en title/CTA slides
- fontFace siempre "Calibri"

PALETA: El usuario te dará un objeto C = { NAVY, DARK, TEAL, GOLD, ICE, WHITE, MUTED, CARD, LIGHT, BORDER }.
Usa ESOS colores constantemente. Nunca inventes colores propios.
Puedes usar tonos complementarios (ej: "4F46E5" morado para segunda categoría) pero mínimo.

RESPONDE ÚNICAMENTE CON EL CÓDIGO JS. Nada de texto ni explicaciones."""


def _load_example() -> str:
    """Load the gold-standard example if available."""
    if os.path.exists(EXAMPLE_PATH):
        with open(EXAMPLE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def call_llm(prompt: str, palette_name: str, output_filename: str) -> str:
    """Call the LLM to generate create.js code."""
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

Genera código al MISMO nivel de detalle visual que el ejemplo. No copies el contenido,
genera contenido NUEVO basado en las instrucciones del usuario, pero con la misma calidad
visual: misma estructura de helpers, mismos patterns de cards/shadows/icons/badges."""

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
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 16000,
        "temperature": 0.7,
    }

    print(f"🎨 Generando con paleta '{palette_name}' ({palette.get('desc', '')})...")
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

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

    if not OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY no configurada")
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
        # Check any .pptx in work_dir
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
