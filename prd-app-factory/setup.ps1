# One-time local setup (Windows PowerShell). Run from the prd-app-factory folder.
$ErrorActionPreference = 'Stop'
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt pytest
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env - add ANTHROPIC_API_KEY before running." }
docker compose up -d
Write-Host "Ready. Try: .\.venv\Scripts\python -m factory run --app rain_demo --prd examples\rain\RAIN_Prototype_Spec_v1.docx --data examples\rain\data"
