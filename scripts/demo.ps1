# scripts/demo.ps1 — Generate mock results and open the dashboard (no API keys needed)
# Usage: .\scripts\demo.ps1

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Model Router Eval — Demo (no API keys required)" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This generates a mock evaluation report with synthetic data"
Write-Host "so you can explore every chart, metric, and output format."
Write-Host ""

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python not found. Install Python 3.9+ from https://python.org" -ForegroundColor Red
    exit 1
}

# Install deps if needed
Write-Host "[1/3] Installing dependencies..." -ForegroundColor Yellow
pip install -e . --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  pip install failed — trying requirements.txt..." -ForegroundColor Yellow
    pip install -r requirements.txt --quiet
}

# Generate mock report
$outputDir = "results/demo"
Write-Host "[2/3] Generating mock evaluation report..." -ForegroundColor Yellow
python scripts/generate_sample_report.py --output-dir $outputDir

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Report generation failed." -ForegroundColor Red
    exit 1
}

# Open dashboard
$dashboard = Join-Path $outputDir "dashboard.html"
if (Test-Path $dashboard) {
    Write-Host "[3/3] Opening dashboard in browser..." -ForegroundColor Yellow
    Start-Process $dashboard
} else {
    Write-Host "[3/3] Dashboard not found at $dashboard" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  Demo complete! Results in: $outputDir/" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor Cyan
Get-ChildItem $outputDir | ForEach-Object { Write-Host "  $_" }
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Explore the dashboard.html in your browser"
Write-Host "  2. Review report.md for a text summary"
Write-Host "  3. Ready for live eval? See docs/how-to-run-live-eval.md"
Write-Host ""
