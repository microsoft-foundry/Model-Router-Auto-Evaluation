# scripts/setup.ps1 — Windows setup script for Model Router Evaluation
# Usage: .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "=== Microsoft Foundry Model Router Evaluation — Setup ===" -ForegroundColor Cyan

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found. Install Python 3.9+ from https://python.org" -ForegroundColor Red
    exit 1
}

$pyVersion = python --version 2>&1
Write-Host "Found $pyVersion"

# Create virtual environment if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

# Install project with dev dependencies
Write-Host "Installing project and dependencies..." -ForegroundColor Yellow
pip install -e ".[dev]" --quiet

# Copy .env.example if .env doesn't exist
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example — edit it with your API keys." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit .env with your Azure endpoints and API keys"
Write-Host "  2. Run:  python scripts/run_eval.py --dry-run"
Write-Host "  3. Run:  python scripts/run_eval.py"
Write-Host ""
Write-Host "Optional — Foundry cloud evaluation:" -ForegroundColor Cyan
Write-Host "  4. pip install -e .[foundry]"
Write-Host "  5. az login"
Write-Host "  6. Add AZURE_AI_PROJECT_ENDPOINT to .env"
Write-Host "  7. python scripts/run_foundry_eval.py --input-dir results/full-eval"
Write-Host ""
