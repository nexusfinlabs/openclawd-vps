#!/bin/bash
# Calendar Status — comprueba si los invitados han aceptado o cancelado
# Usage: calendar-status "término_de_búsqueda"

cd /home/albi_agent/openclawd_stack || exit 1
set -a; source .env 2>/dev/null; set +a
export GOOGLE_APPLICATION_CREDENTIALS="/home/albi_agent/.secrets/google/credentials.json"
export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"

# Detect channel from env (OpenClaw sets OC_CHANNEL) or default to whatsapp
CHANNEL="${OC_CHANNEL:-whatsapp}"
if [[ "$CHANNEL" == "telegram" ]]; then
    TARGET="7024795874"
else
    TARGET="34605693177"
fi

QUERY="$1"
if [[ -z "$QUERY" ]]; then
    # Default search for future events if no query provided
    QUERY=""
fi

echo "⏳ Consultando estado de eventos para '$QUERY'..."
RESULT=$(python3 ops/calendar_manager.py --action status --query "$QUERY" 2>&1)

# Print to stdout
echo "$RESULT"

# Send to chat
openclaw message send --channel "$CHANNEL" --target "$TARGET" \
    --message "🗓️ **Estado de Invitaciones:**
$RESULT" 2>/dev/null && echo "✅ Estado enviado por $CHANNEL"
