#!/bin/bash
# Generate professional PDF + DOCX documents and send them via WhatsApp/Telegram.
# Usage: ./generate-doc.sh "SOW" "Full text content of the document"
# Usage: ./generate-doc.sh "NDA" "Full text content" "telegram"

doc_type=$1
content=$2
channel="${3:-whatsapp}"  # default to whatsapp, can be "telegram"

if [[ -z "$doc_type" || -z "$content" ]]; then
  echo "ERROR: Document type and content are required."
  echo "Usage: generate-doc.sh <DOC_TYPE> <CONTENT> [channel]"
  exit 1
fi

cd ~/openclawd_stack || exit 1

# 1. Generate PDF + DOCX inside the Docker container
output=$(sudo -n docker exec oc_api python /app/document_generator_cli.py "$doc_type" "$content" 2>&1)
echo "$output"

# 2. Extract filenames from structured output
pdf_file=$(echo "$output" | grep "^PDF_FILE:" | cut -d: -f2)
docx_file=$(echo "$output" | grep "^DOCX_FILE:" | cut -d: -f2)

if [[ -z "$pdf_file" || -z "$docx_file" ]]; then
    echo "ERROR: No se pudieron generar los documentos."
    exit 1
fi

# 3. Fix ownership so OpenClaw can read the files
sudo -n chown -R albi_agent:albi_agent ~/.openclaw/workspace/docs/ 2>/dev/null

pdf_path="$HOME/.openclaw/workspace/docs/drafts/$pdf_file"
docx_path="$HOME/.openclaw/workspace/docs/drafts/$docx_file"

# 4. Determine target based on channel
if [[ "$channel" == "telegram" ]]; then
    target="7024795874"
else
    target="34605693177"
fi

# 5. Send BOTH files via OpenClaw CLI
export PATH=$HOME/.nvm/versions/node/v22.22.0/bin:$PATH

echo "Enviando PDF a $channel..."
openclaw message send --channel "$channel" --target "$target" \
    --message "📄 *${doc_type}* — PDF generado:" --media "$pdf_path"

echo "Enviando DOCX a $channel..."
openclaw message send --channel "$channel" --target "$target" \
    --message "📝 *${doc_type}* — Word (DOCX) generado:" --media "$docx_path"

echo "SUCCESS: Ambos archivos (PDF + DOCX) enviados al usuario por $channel."
