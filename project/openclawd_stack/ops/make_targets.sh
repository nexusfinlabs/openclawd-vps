#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/openclawd_stack"
STATE="$ROOT/state"
TARGETS="$STATE/targets.txt"

mkdir -p "$STATE"

RAW="$STATE/targets_raw.txt"
OUT="$STATE/targets_extracted.txt"

openclaw agent --agent main --thinking medium --message '
Generate 150 official firm websites for Texas-based Private Equity firms, Independent Sponsors, and M&A Advisory firms (Dallas, Houston, Austin, San Antonio).
IMPORTANT: include the full URL with https:// for each website.
Return plain text. No need to be strict with formatting.
' > "$RAW"

grep -oE 'https?://[^ )"]+' "$RAW" \
  | sed 's/[",.]$//' \
  | sed 's#/$##' \
  | sort -u \
  | head -n 100 > "$OUT"

mv "$OUT" "$TARGETS"

echo "Wrote: $TARGETS"
wc -l "$TARGETS"
head -n 5 "$TARGETS"
