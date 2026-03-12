#!/bin/bash
# Enrich a B2B contact's email address
# Usage: ./enrich-email.sh "Juan" "Perez" "acme.com"

if [ "$#" -ne 3 ]; then
  echo "Uso: ./enrich-email.sh <nombre> <apellido> <dominio>"
  exit 1
fi

FIRST=$1
LAST=$2
DOMAIN=$3

# Ensure we're running in the right directory and with right python
cd /home/albi_agent/openclawd_stack || exit 1

# Activate virtualenv if there's one, or use system python
echo "Ejecutando waterfall de enriquecimiento para $FIRST $LAST en $DOMAIN..."

# Assuming python3 is available and packages installed globally or in venv
python3 ops/email_enricher.py "$FIRST" "$LAST" "$DOMAIN"
