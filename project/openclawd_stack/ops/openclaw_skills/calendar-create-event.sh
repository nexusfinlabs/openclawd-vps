#!/bin/bash
# Crea un evento ICS y envíalo a invitados
# Usage: ./calendar-create-event.sh "Título" "2026-03-12T16:00:00Z" "invitado1@ejemplo.com, invitado2@ejemplo.com"

cd /home/albi_agent/openclawd_stack
set -a
source .env 2>/dev/null
set +a
export GOOGLE_APPLICATION_CREDENTIALS="/home/albi_agent/.secrets/google/credentials.json"

title=$1
datetime=$2
emails=$3

# Handle target and channel
CHANNEL="${OC_CHANNEL:-whatsapp}"
TARGET="${OC_TARGET:-34605693177}"

if [ -z "$title" ] || [ -z "$datetime" ] || [ -z "$emails" ]; then
    echo "❌ Faltan parámetros. Uso: ./calendar-create-event.sh 'Título' 'Fecha_ISO' 'emails,separados,por,coma'"
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "❌ Necesito el título, la fecha/hora y los correos de los invitados para crear el evento." 2>/dev/null
    exit 1
fi

echo "⏳ Creando el evento y enviando invitaciones a $emails..."

output=$(python3 ops/calendar_manager.py --action create --title "$title" --datetime "$datetime" --emails "$emails" 2>&1)

if echo "$output" | grep -q "✅ Invite sent to"; then
    echo "$output"
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "✅ He creado el evento '$title' y he enviado la invitación con el ICS adjunto a: $emails" 2>/dev/null
else
    echo "$output"
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "❌ Hubo un problema al crear y enviar el evento. Verifica tus SMTP credentials." 2>/dev/null
fi
