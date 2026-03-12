#!/bin/bash
# Sube archivo ICS al calendario
# Usage: ./calendar-upload-ics.sh "/ruta/al/archivo.ics"

cd /home/albi_agent/openclawd_stack
source .env 2>/dev/null

ics_file=$1

# Handle target and channel
CHANNEL="${OC_CHANNEL:-whatsapp}"
TARGET="${OC_TARGET:-34605693177}"

if [ -z "$ics_file" ] || [ ! -f "$ics_file" ]; then
    echo "❌ Debes especificar la ruta a un archivo .ics válido."
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "❌ No encuentro el archivo ICS que me has pasado." 2>/dev/null
    exit 1
fi

echo "⏳ Añadiendo evento a tu Google Calendar..."

# Run the python script
output=$(python3 ops/calendar_manager.py --action add_file --file "$ics_file" 2>&1)

if echo "$output" | grep -q "✅ Event created successfully"; then
    echo "$output"
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "✅ He añadido el evento de ese archivo directamente a tu Google Calendar." 2>/dev/null
else
    echo "$output"
    openclaw message send --channel "$CHANNEL" --target "$TARGET" --message "❌ Hubo un error al intentar añadir el evento. Revisa logs." 2>/dev/null
fi
