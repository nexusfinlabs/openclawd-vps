#!/bin/bash
# Proposal Sender — envía el último borrador generado por email
# Usage: send-proposal [email_destinatario]

cd /home/albi_agent/openclawd_stack || exit 1
set -a; source .env 2>/dev/null; set +a
export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"

# Target configuration
CHANNEL="whatsapp"
TARGET="34605693177"

# Clean arguments from smart quotes
DEST=$(echo "$1" | sed 's/[“”"'\'']//g' | xargs)

# Fallback: if no email provided, check if we have one (not common in this flow)
if [[ -z "$DEST" ]]; then
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "⚠️ Falta el email del destinatario.\nUso: !send-proposal \"email@ejemplo.com\""
    exit 1
fi

openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "🚀 **Iniciando Envío de Mail**\nPara: $DEST\nBCC: dealflow@nexusfinlabs.com"

# Check for draft
if [[ ! -f /tmp/last_proposal.txt ]]; then
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "❌ Error: No se encontró ningún borrador previo. Usa !make-proposal primero."
    exit 1
fi

# Send the email using the manager
RESULT=$(python3 ops/proposal_manager.py --send "$DEST" "/tmp/last_proposal.txt" 2>> /tmp/proposal_debug.log)
py_status=$?

if [ $py_status -ne 0 ] || [[ "$RESULT" == ERROR* ]]; then
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "❌ **Fallo en el servidor de correo:**\n$RESULT"
    exit 1
fi

# Success feedback
openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "✅ **¡Mail enviado con éxito!**\n\nEl destinatario ($DEST) debería recibirlo en breve. Se ha enviado una copia a Dealflow."

echo "Sent $DEST"
