#!/bin/bash
# Draft a professional email based on the context provided.
# Usage: ./draft-email.sh "Company Name" "target@email.com" "Target Name" "high|medium" "Custom context..."

target_email=$2
target_name=$3

# Simple validation so LLM doesn't pass random crap
if [[ "$target_email" == "unknown" || "$target_email" == "" ]]; then
  echo "ERROR: Target email is missing or unknown. Cannot draft email."
  exit 1
fi

if [[ "$target_name" == "unknown" || "$target_name" == "" ]]; then
  target_name="Equipo"
fi

cd ~/openclawd_stack || exit 1
# Execute the synchronous drafting logic with injected sudo logic for frictionless WhatsApp usage
sudo -n docker exec oc_api python email_drafter.py "$1" "$target_email" "$target_name" "$4" "$5"
