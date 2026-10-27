#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/home/Cohorte5/SismoWatch.zip}"

cd "$ROOT"
rm -f "$OUT"
zip -r "$OUT" . \
  -x ".env" \
  -x "AGENTS.md" \
  -x ".git/*" \
  -x "*/node_modules/*" \
  -x "*/dist/*" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x "*.tsbuildinfo" \
  -x "*/.pytest_cache/*" >/dev/null

echo "Paquete: $OUT"
unzip -l "$OUT" | tail -3
