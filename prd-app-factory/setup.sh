#!/usr/bin/env bash
# One-time local setup (macOS / Linux / Git Bash). Run from the prd-app-factory folder.
set -euo pipefail
[ -d .venv ] || python3 -m venv .venv
PY=.venv/bin/python; [ -x "$PY" ] || PY=.venv/Scripts/python
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt pytest
[ -f .env ] || { cp .env.example .env; echo "Created .env - add ANTHROPIC_API_KEY before running."; }
docker compose up -d
echo "Ready. Try: $PY -m factory run --app rain_demo --prd examples/rain/RAIN_Prototype_Spec_v1.docx --data examples/rain/data"
