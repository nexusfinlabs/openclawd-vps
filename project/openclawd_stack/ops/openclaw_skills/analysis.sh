#!/bin/bash
# analysis.sh — Deep analysis of a URL/website
#
# Usage:
#   analysis.sh https://norgine.com/clinical-trial-disclosure/
#   analysis.sh https://norgine.com/ "busco ensayos fase 3"
#   analysis.sh --context norgine https://example.com

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

# ── Resolve context file (same logic as make-ppt.sh) ──
resolve_context() {
  local name="$1"
  local base="${name%.md}"
  base="${base%.pdf}"
  local PROJECT_CTX="/home/albi_agent/openclawd_stack/context"
  local candidates=(
    "$PROJECT_CTX/${base}.md"
    "$PROJECT_CTX/${base}.pdf"
    "$PROJECT_CTX/${name}"
    "$CONTEXT_DIR/${base}.md"
    "$CONTEXT_DIR/${base}.pdf"
    "$CONTEXT_DIR/${name}"
    "$WORKSPACE/${base}.md"
    "$WORKSPACE/${base}.pdf"
    "$WORKSPACE/${name}"
  )
  for f in "${candidates[@]}"; do
    [ -f "$f" ] && echo "$f" && return 0
  done
  return 1
}

# Parse flags
CONTEXT_NAME=""
ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context) CONTEXT_NAME="$2"; shift 2 ;;
    *)         ARGS+=("$1"); shift ;;
  esac
done

if [ ${#ARGS[@]} -eq 0 ]; then
  openclaw message send --channel "$CHANNEL" --target "$TARGET" \
    --message "❌ Uso:
\`!analysis https://example.com\`
\`!analysis https://example.com contexto\`
\`!analysis --context norgine https://example.com\`"
  exit 1
fi

URL="${ARGS[0]}"
EXTRA_CONTEXT="${ARGS[*]:1}"

# Add named context if requested
if [ -n "$CONTEXT_NAME" ]; then
  CTX_FILE=$(resolve_context "$CONTEXT_NAME")
  if [ -n "$CTX_FILE" ]; then
    if [[ "$CTX_FILE" == *.pdf ]]; then
      STORED=$(python3 -c "
from markitdown import MarkItDown
m = MarkItDown()
r = m.convert('$CTX_FILE')
print(r.text_content)
" 2>/dev/null || cat "$CTX_FILE")
    else
      STORED=$(cat "$CTX_FILE")
    fi
    EXTRA_CONTEXT="$STORED $EXTRA_CONTEXT"
  else
    openclaw message send --channel "$CHANNEL" --target "$TARGET" \
      --message "❌ No encuentro contexto \`$CONTEXT_NAME\`. Usa \`!context-list\`."
    exit 1
  fi
fi

# Acknowledge
openclaw message send --channel "$CHANNEL" --target "$TARGET" \
  --message "🔍 Analizando: \`$URL\`
Esto puede tardar 30-60s (scraping + análisis LLM)..."

# Run analyzer
if [ -n "$EXTRA_CONTEXT" ]; then
  output=$(python3 "$OPS_DIR/ops/web_analyzer.py" "$URL" "$EXTRA_CONTEXT" 2>&1)
else
  output=$(python3 "$OPS_DIR/ops/web_analyzer.py" "$URL" 2>&1)
fi

# Send result
openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "$output"

# Send report file if generated
report_path=$(echo "$output" | grep -o '/home/.*\.md' | head -1)
if [ -n "$report_path" ] && [ -f "$report_path" ]; then
  openclaw message send --channel "$CHANNEL" --target "$TARGET" --media "$report_path"
fi
