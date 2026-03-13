#!/bin/bash
# make-ppt.sh — Generate professional presentations
#
# Usage:
#   make-ppt.sh "5 slides sobre AI en payments"                      → PptxGenJS (default)
#   make-ppt.sh --template 3 "5 slides sobre AI"                    → Template 3.pptx
#   make-ppt.sh --context norgine --template 5 "10 slides para VP"  → Context file + template
#   make-ppt.sh --palette dark-premium "5 slides"                    → PptxGenJS with palette
#   make-ppt.sh --html "5 slides sobre AI"                          → Reveal.js HTML

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

# ── Resolve context file (searches multiple locations) ──
resolve_context() {
  local name="$1"
  local base="${name%.md}"  # strip .md if provided
  base="${base%.pdf}"       # strip .pdf if provided

  # Search paths (in priority order)
  local candidates=(
    "$CONTEXT_DIR/${base}.md"
    "$CONTEXT_DIR/${base}.pdf"
    "$CONTEXT_DIR/${name}"
    "$WORKSPACE/${base}.md"
    "$WORKSPACE/${base}.pdf"
    "$WORKSPACE/${name}"
  )

  for f in "${candidates[@]}"; do
    if [ -f "$f" ]; then
      echo "$f"
      return 0
    fi
  done
  return 1
}

# Parse flags
FORMAT="pptx"
PALETTE="navy-executive"
TEMPLATE=""
CONTEXT_NAME=""
ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --html)       FORMAT="html"; shift ;;
    --palette)    PALETTE="$2"; shift 2 ;;
    --template)   TEMPLATE="$2"; shift 2 ;;
    --context)    CONTEXT_NAME="$2"; shift 2 ;;
    *)            ARGS+=("$1"); shift ;;
  esac
done

# Validate
if [ ${#ARGS[@]} -eq 0 ]; then
  openclaw message send --channel "$CHANNEL" --target "$TARGET" \
    --message "❌ Uso:
\`!make-ppt 5 slides sobre AI\`
\`!make-ppt --template 3 5 slides\`
\`!make-ppt --context norgine --template 5 10 slides\`

📁 Templates: 1-10 | Contextos: \`!context-list\`"
  exit 1
fi

request="${ARGS[*]}"

# ── Build prompt (with optional named context) → temp file ──
PROMPT_FILE=$(mktemp /tmp/ppt_prompt_XXXXXX.txt)
trap "rm -f '$PROMPT_FILE'" EXIT

if [ -n "$CONTEXT_NAME" ]; then
  CTX_FILE=$(resolve_context "$CONTEXT_NAME")
  if [ -z "$CTX_FILE" ]; then
    openclaw message send --channel "$CHANNEL" --target "$TARGET" \
      --message "❌ No encuentro contexto \`$CONTEXT_NAME\`.
Busqué en: context/ y workspace/
Usa \`!context-list\` para ver disponibles."
    exit 1
  fi

  # Read content (handle PDF via python if needed)
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
  echo "📝 Context '$(basename "$CTX_FILE")' loaded ($(wc -c < "$PROMPT_FILE") chars)"
else
  echo "$request" > "$PROMPT_FILE"
fi

# ── Generate ──────────────────────────────────────────
if [ "$FORMAT" = "html" ]; then
  output=$(python3 "$OPS_DIR/ops/revealjs_generator.py" --prompt-file "$PROMPT_FILE" 2>&1)
  file_path=$(echo "$output" | grep -o '/home/.*\.html' | head -1)

elif [ -n "$TEMPLATE" ]; then
  output=$(python3 "$OPS_DIR/ops/ppt_generator.py" --prompt-file "$PROMPT_FILE" --template "$TEMPLATE" 2>&1)
  file_path=$(echo "$output" | grep -o '/home/.*\.pptx' | head -1)

else
  output=$(node "$OPS_DIR/ops/ppt_generator.js" --prompt-file "$PROMPT_FILE" --palette "$PALETTE" 2>&1)
  file_path=$(echo "$output" | grep -o '/home/.*\.pptx' | head -1)
fi

# Send summary
openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "$output"

# Send the file if generated
if [ -n "$file_path" ] && [ -f "$file_path" ]; then
  openclaw message send --channel "$CHANNEL" --target "$TARGET" --media "$file_path"
fi
