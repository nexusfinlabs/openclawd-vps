#!/bin/bash
# Proposal Drafter — genera borrador de propuesta y lo envía por WhatsApp
# Usage: make-proposal [destinatario] [contexto...]

cd /home/albi_agent/openclawd_stack || exit 1
set -a; source .env 2>/dev/null; set +a
export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"

# Target configuration
CHANNEL="whatsapp"
TARGET="34605693177"

# Clean first argument (recipient) from all types of quotes
DEST=$(echo "$1" | sed 's/[“”"'\'']//g' | xargs)

# Shift to remove the first argument
shift

# Capture ALL remaining arguments as the context, stripping smart quotes
RAW_CONTEXT=$(echo "$*" | sed 's/[“”]//g' | xargs)

# Debug: check what we received
echo "[$(date)] make-proposal.sh - ARG_COUNT: $#" >> /tmp/proposal_debug.log
echo "[$(date)] \$1: $1" >> /tmp/proposal_debug.log
echo "[$(date)] \$2: $2" >> /tmp/proposal_debug.log
echo "[$(date)] \$*: $*" >> /tmp/proposal_debug.log

# Debug: check RAW_CONTEXT
echo "[$(date)] Processed RAW_CONTEXT: $RAW_CONTEXT" >> /tmp/proposal_debug.log
echo "[$(date)] DEST: $DEST, CONTEXT_LEN: ${#RAW_CONTEXT}" >> /tmp/proposal_debug.log

# Stage 2: AI Generation
# Pass the cleaned context to python
DRAFT=$(python3 ops/proposal_manager.py --make "$DEST" "$RAW_CONTEXT" 2>> /tmp/proposal_debug.log)
py_status=$?

if [ $py_status -ne 0 ] || [[ "$DRAFT" == Error* ]]; then
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "❌ **Error en Generación AI:** $DRAFT"
    exit 1
fi

# Stage 3: Results
echo "$DRAFT" > /tmp/last_proposal.txt
echo "[$(date)] Draft generated successfully" >> /tmp/proposal_debug.log

cat > /tmp/outbound_msg.txt <<EOF
📝 **Paso 3/3: Borrador Generado con Éxito**

$DRAFT

---
💡 **Para enviar este Mail:**
!send-proposal "$DEST"
EOF

openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "$(cat /tmp/outbound_msg.txt)"

echo "Done"
