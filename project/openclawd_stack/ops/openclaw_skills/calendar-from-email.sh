#!/bin/bash
# Busca evento ICS en el correo y añádelo a Google Calendar
# Usage: ./calendar-from-email.sh "Nombre o Email del remitente"

cd /home/albi_agent/openclawd_stack
source .env 2>/dev/null

query=$1

# Handle target and channel
CHANNEL="${OC_CHANNEL:-whatsapp}"
TARGET="${OC_TARGET:-34605693177}"

if [ -z "$query" ]; then
    echo "❌ Debes especificar un término de búsqueda (ej. el nombre o correo del remitente)."
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "❌ Faltan parámetros para buscar el evento en tu correo." 2>/dev/null
    exit 1
fi

echo "⏳ Buscando eventos de '$query' en tus buzones..."

# Run the python script and capture output
output=$(python3 ops/calendar_manager.py --action fetch_inbox --query "$query" 2>&1)

if echo "$output" | grep -q "✅ Successfully extracted and added event"; then
    echo "$output"
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "✅ He encontrado el evento de '$query' en tu bandeja de entrada y lo he añadido a tu Google Calendar." 2>/dev/null
else
    echo "$output"
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "❌ No he podido encontrar ningún evento reciente de '$query' en tus correos, o hubo un error al añadirlo." 2>/dev/null
fi
