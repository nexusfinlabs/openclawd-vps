#!/bin/bash
# Wrapper for the OpenClaw native skill to draft emails.
# Usage: ./draft_email.sh "Acme Corp" "ceo@acme.com" "John Doe" "high" "Met them at the M&A Texas conference."

# Run the python drafter inside the container
cd ~/openclawd_stack || exit 1

# Execute inside the running oc_api container
sudo docker exec oc_api python email_drafter.py "$1" "$2" "$3" "$4" "$5"
