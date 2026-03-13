#!/bin/bash
# make-ppt.sh — Genera presentaciones profesionales (LLM → PptxGenJS)
#
# Cada presentación es ÚNICA: el LLM genera un create.js a medida.
#
# Uso desde WhatsApp/Telegram:
#   !make-ppt 5 slides sobre AI en pharma
#   !make-ppt --context norgine 10 slides para VP IT
#   !make-ppt --palette tech 5 slides sobre payments
#   !make-ppt --context norgine --palette executive 10 slides
#
# Palettes: pharma (default), tech, bold, trust, executive

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
  local PROJECT_CTX="/home/albi_agent/openclawd_stack/context"
  for f in "$PROJECT_CTX/${base}.md" "$PROJECT_CTX/${base}.pdf" "$PROJECT_CTX/${name}" \
           "$CONTEXT_DIR/${base}.md" "$CONTEXT_DIR/${base}.pdf" "$CONTEXT_DIR/${name}" \
           "$WORKSPACE/${base}.md" "$WORKSPACE/${base}.pdf" "$WORKSPACE/${name}"; do
    [ -f "$f" ] && echo "$f" && return 0
  done
  return 1
}

# Parse flags
PALETTE="pharma"
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
\`!make-ppt --palette tech 5 slides\`

🎨 Paletas: pharma, tech, bold, trust, executive"
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

# ── Generate with LLM → PptxGenJS ──
output=$(python3 "$OPS_DIR/ops/ppt_dynamic.py" --prompt-file "$PROMPT_FILE" --palette "$PALETTE" 2>&1)
exit_code=$?
file_path=$(echo "$output" | grep -o '/home/.*\.pptx' | head -1)

if [ $exit_code -ne 0 ] || [ -z "$file_path" ] || [ ! -f "$file_path" ]; then
  openclaw message send --channel "$CHANNEL" --target "$TARGET" \
    --message "❌ Error generando PPT:
$(echo "$output" | tail -5)"
  exit 1
fi

# Copy to docs/ for local sync (rsync pulls this to local)
DOCS_DIR="/home/albi_agent/openclawd_stack/docs"
mkdir -p "$DOCS_DIR"
cp "$file_path" "$DOCS_DIR/" 2>/dev/null || true

# Send summary
size_kb=$(( $(stat -c%s "$file_path" 2>/dev/null || echo 0) / 1024 ))
openclaw message send --channel "$CHANNEL" --target "$TARGET" \
  --message "✅ PPT generada (${size_kb} KB, paleta: $PALETTE)
📎 Enviando archivo..."

# Send the PPTX file as attachment
openclaw message send --channel "$CHANNEL" --target "$TARGET" --media "$file_path"
