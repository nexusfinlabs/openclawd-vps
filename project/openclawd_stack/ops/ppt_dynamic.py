#!/usr/bin/env python3
"""
ppt_dynamic.py — LLM-powered PptxGenJS presentation generator.

Flow:
  1. Reads prompt (+ optional context)
  2. Calls LLM with expert PptxGenJS system prompt
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
MODEL = "anthropic/claude-sonnet-4"  # Fast + good at code gen
DRAFTS_DIR = "/home/albi_agent/.openclaw/workspace"

PALETTES = {
    "pharma":    {"NAVY": "0A1628", "TEAL": "00A896", "GOLD": "F0C040", "ICE": "C8E6E3", "WHITE": "FFFFFF", "MUTED": "7A8BA5"},
    "tech":      {"DARK": "0F1923", "CARD": "1A2535", "TEAL": "02C39A", "AMBER": "F59E0B", "WHITE": "FFFFFF", "MUTED": "8899AA"},
    "bold":      {"CHARCOAL": "1E2022", "ORANGE": "E85D26", "SAND": "F5EFE6", "WHITE": "FFFFFF", "MUTED": "9A9A9A", "TEAL": "2A9D8F"},
    "trust":     {"NAVY": "1E2761", "ICE": "CADCFC", "TEAL": "028090", "WHITE": "FFFFFF", "MUTED": "7A8BA5", "GOLD": "E8B931"},
    "executive": {"DARK": "0D1117", "CARD": "161B22", "GREEN": "238636", "MUTED": "8B949E", "WHITE": "FFFFFF", "TEAL": "238636"},
}

SYSTEM_PROMPT = r"""Eres un experto en crear presentaciones PowerPoint profesionales con pptxgenjs.

Cuando el usuario te pase instrucciones, generas un create.js completo y ejecutable.

REGLAS TÉCNICAS OBLIGATORIAS:
- Layout siempre LAYOUT_16x9 (10" x 5.625")
- Todo el código dentro de async function main()
- Helper iconBase64() siempre incluido
- Colores sin # (ej: "1B2B5E" no "#1B2B5E")
- shadow con opacity separado, nunca en hex
- margin: 0 en textos alineados con shapes
- Bullets con { bullet: true }, nunca "• " unicode
- Usar factory function para shadows: const mkS = () => ({...})
- Guardar con: await pres.writeFile({ fileName: "OUTPUT_FILENAME" })
- Sin markdown, sin explicaciones — solo código JS puro ejecutable
- IMPORTANTE: la primera línea debe ser: const PptxGenJS = require("pptxgenjs");

ESTRUCTURA OBLIGATORIA DE SLIDES:
1. Title slide — fondo oscuro, barra lateral, supertítulo, título grande, chips
2. Resumen / métricas — 3 números grandes con iconos
3. Tabla o datos — tabla visual con badges de color
4. Split — dos paneles comparando áreas o categorías
5. Cards — 4 cards con iconos, números, descripción
6. Proceso / pasos — filas numeradas con iconos
7. CTA / Next Steps — fondo oscuro, pasos con círculos numerados

Puedes añadir slides adicionales si el usuario lo pide (8, 10, 15 slides etc).

DISEÑO OBLIGATORIO EN CADA SLIDE:
- Barra lateral izquierda (motivo visual consistente)
- Header con sección + título (excepto title y CTA)
- Footer en todas las slides
- Iconos como círculos de color con texto emoji o letra
- Cards con sombra (shape offset +0.04)
- Jerarquía tipográfica: título 40-52pt, sección 8-9pt charSpacing 3, body 9-11pt
- Nunca texto-only, siempre elemento visual
- Nunca línea decorativa bajo títulos

RESPONDE ÚNICAMENTE CON EL CÓDIGO JS. Nada más. Sin ```javascript, sin explicaciones."""


def call_llm(prompt: str, palette_name: str, output_filename: str) -> str:
    """Call the LLM to generate create.js code."""
    palette = PALETTES.get(palette_name, PALETTES["pharma"])
    palette_str = json.dumps(palette, indent=2)

    user_message = f"""Genera un create.js completo para esta presentación.

PALETA A USAR (obligatorio):
{palette_str}

NOMBRE DEL ARCHIVO DE SALIDA: "{output_filename}"

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

    print(f"🎨 Generando presentación con paleta '{palette_name}'...")
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    # Extract JS code — strip markdown fences if present
    code = content.strip()
    if code.startswith("```"):
        # Remove first and last fence lines
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

    # Read prompt
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

    # Write create.js to temp file
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
            # Save the JS for debugging
            debug_path = os.path.join(DRAFTS_DIR, f"debug_create_{timestamp}.js")
            with open(debug_path, "w") as f:
                f.write(js_code)
            print(f"🔍 JS guardado para debug: {debug_path}")
            sys.exit(1)

        print(result.stdout)

    except subprocess.TimeoutExpired:
        print("❌ Timeout ejecutando create.js (60s)")
        sys.exit(1)

    # Find the generated .pptx
    generated_path = os.path.join(work_dir, output_filename)
    if os.path.exists(generated_path):
        # Move to drafts
        import shutil
        shutil.move(generated_path, output_path)
        size_kb = os.path.getsize(output_path) / 1024
        print(f"✅ Presentación generada: {output_path} ({size_kb:.0f} KB)")
    else:
        # Check if it landed somewhere else
        for f in os.listdir(work_dir):
            if f.endswith(".pptx"):
                shutil.move(os.path.join(work_dir, f), output_path)
                size_kb = os.path.getsize(output_path) / 1024
                print(f"✅ Presentación generada: {output_path} ({size_kb:.0f} KB)")
                break
        else:
            print(f"❌ No se encontró archivo .pptx en {work_dir}")
            print(f"Archivos: {os.listdir(work_dir)}")
            sys.exit(1)


if __name__ == "__main__":
    main()
