#!/bin/bash
# make-ppt.sh — Genera presentaciones profesionales (PptxGenJS)
#
# Uso desde WhatsApp/Telegram:
#   !make-ppt 5 slides sobre AI en pharma
#   !make-ppt --context norgine 10 slides para VP IT
#   !make-ppt --palette dark-premium 5 slides sobre payments
#
# Palettes: navy-executive (default), dark-premium, clean-bold, midnight, teal-trust

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPS_DIR="$(dirname "$SCRIPT_DIR")"
export PATH="/home/albi_agent/.nvm/versions/node/v22.22.0/bin:$PATH"

# Load env
[ -f "$OPS_DIR/.env" ] && set -a && source "$OPS_DIR/.env" && set +a

TARGET="${SENDER_TARGET:-34605693177}"
CHANNEL="${SENDER_CHANNEL:-whatsapp}"
WORKSPACE="/home/albi_agent/.openclaw/workspace"
CONTEXT_DIR="$WORKSPACE/context"

# ── Resolve context file ──
resolve_context() {
  local name="$1"
  local base="${name%.md}"
  base="${base%.pdf}"
  for f in "$CONTEXT_DIR/${base}.md" "$CONTEXT_DIR/${base}.pdf" "$CONTEXT_DIR/${name}" \
           "$WORKSPACE/${base}.md" "$WORKSPACE/${base}.pdf" "$WORKSPACE/${name}"; do
    [ -f "$f" ] && echo "$f" && return 0
  done
  return 1
}

# Parse flags
PALETTE="navy-executive"
CONTEXT_NAME=""
ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --palette)  PALETTE="$2"; shift 2 ;;
    --context)  CONTEXT_NAME="$2"; shift 2 ;;
    *)          ARGS+=("$1"); shift ;;
  esac
done

if [ ${#ARGS[@]} -eq 0 ]; then
  openclaw message send --channel "$CHANNEL" --target "$TARGET" \
    --message "❌ Uso:
\`!make-ppt 5 slides sobre AI en pharma\`
\`!make-ppt --context norgine 10 slides para VP IT\`
\`!make-ppt --palette dark-premium 5 slides\`

🎨 Paletas: navy-executive, dark-premium, clean-bold, midnight, teal-trust"
  exit 1
fi

request="${ARGS[*]}"

# ── Build prompt → temp file ──
PROMPT_FILE=$(mktemp /tmp/ppt_prompt_XXXXXX.txt)
trap "rm -f '$PROMPT_FILE'" EXIT

if [ -n "$CONTEXT_NAME" ]; then
  CTX_FILE=$(resolve_context "$CONTEXT_NAME") || true
  if [ -z "$CTX_FILE" ]; then
    openclaw message send --channel "$CHANNEL" --target "$TARGET" \
      --message "❌ No encuentro contexto \`$CONTEXT_NAME\`.
Busqué en: context/ y workspace/
Usa \`!context-list\` para ver disponibles."
    exit 1
  fi

  if [[ "$CTX_FILE" == *.pdf ]]; then
    CTX_CONTENT=$(python3 -c "
from markitdown import MarkItDown
m = MarkItDown()
r = m.convert('$CTX_FILE')
print(r.text_content)
" 2>/dev/null || cat "$CTX_FILE")
  else
    CTX_CONTENT=$(cat "$CTX_FILE")
  fi

  cat > "$PROMPT_FILE" <<PROMPT_EOF
Basándote en el siguiente contexto, genera la presentación.

--- CONTEXTO ($(basename "$CTX_FILE")) ---
$CTX_CONTENT
--- FIN CONTEXTO ---

Instrucciones: $request
PROMPT_EOF
else
  echo "$request" > "$PROMPT_FILE"
fi

# ── Generate with PptxGenJS ──
output=$(node "$OPS_DIR/ops/ppt_generator.js" --prompt-file "$PROMPT_FILE" --palette "$PALETTE" 2>&1)
file_path=$(echo "$output" | grep -o '/home/.*\.pptx' | head -1)

# Send summary
openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "$output"

# Send the PPTX file
if [ -n "$file_path" ] && [ -f "$file_path" ]; then
  openclaw message send --channel "$CHANNEL" --target "$TARGET" --media "$file_path"
else
  openclaw message send --channel "$CHANNEL" --target "$TARGET" \
    --message "⚠️ No se pudo generar el archivo. Output:
$(echo "$output" | tail -5)"
fi
