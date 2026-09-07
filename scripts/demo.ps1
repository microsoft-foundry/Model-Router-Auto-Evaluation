# scripts/demo.ps1 — Generate mock results or run a live Foundry evaluation
# Usage:
#   .\scripts\demo.ps1
#   .\scripts\demo.ps1 -Live
#   .\scripts\demo.ps1 -Live -Resume

param(
    [switch]$Live,
    [switch]$Resume
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$venvPip = Join-Path $projectRoot ".venv\Scripts\pip.exe"
$envFile = Join-Path $projectRoot ".env"

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
if ($Live) {
    Write-Host "  Model Router Eval — LIVE Foundry Demo" -ForegroundColor Cyan
} else {
    Write-Host "  Model Router Eval — Demo (no API keys required)" -ForegroundColor Cyan
}
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# Always run in the repository virtual environment.
if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: .venv not found. Create it with: python -m venv .venv" -ForegroundColor Red
    exit 1
}

if ($Live -and -not (Test-Path $envFile)) {
    Write-Host "ERROR: .env not found." -ForegroundColor Red
    Write-Host "Create it with: Copy-Item .env.example .env" -ForegroundColor Yellow
    Write-Host "Then add your deployed model endpoints, keys, and deployment names." -ForegroundColor Yellow
    exit 1
}

# Install deps if needed
Write-Host "[1/3] Installing dependencies..." -ForegroundColor Yellow
& $venvPip install -e $projectRoot --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  pip install failed — trying requirements.txt..." -ForegroundColor Yellow
    & $venvPip install -r (Join-Path $projectRoot "requirements.txt") --quiet
}

Push-Location $projectRoot
try {
    if ($Live) {
        Write-Host "This calls real deployments and consumes billable tokens." -ForegroundColor Yellow
        Write-Host "Loading endpoints, keys, and deployment names from .env."
        Write-Host ""

        Write-Host "[2/3] Running live 25-prompt evaluation..." -ForegroundColor Yellow
        $evalArgs = @("scripts\run_eval.py", "--config", "configs\live_demo.yaml")
        if ($Resume) {
            $evalArgs += "--resume"
        }
        & $venvPython @evalArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Live evaluation failed."
        }

        $outputDir = Get-ChildItem (Join-Path $projectRoot "results") -Directory |
            Where-Object { $_.Name -match '^run-\d+$' } |
            Sort-Object Name -Descending |
            Select-Object -First 1
    } else {
        Write-Host "This generates a mock evaluation report with synthetic data"
        Write-Host "so you can explore every chart, metric, and output format."
        Write-Host ""

        $outputPath = Join-Path $projectRoot "results\demo"
        Write-Host "[2/3] Generating mock evaluation report..." -ForegroundColor Yellow
        & $venvPython scripts\generate_sample_report.py --output-dir $outputPath
        if ($LASTEXITCODE -ne 0) {
            throw "Report generation failed."
        }
        $outputDir = Get-Item $outputPath
    }

    if (-not $outputDir) {
        throw "Could not locate the evaluation output directory."
    }

    # Open dashboard
    $dashboard = Join-Path $outputDir.FullName "dashboard.html"
    if (Test-Path $dashboard) {
        Write-Host "[3/3] Opening dashboard in browser..." -ForegroundColor Yellow
        Start-Process $dashboard
    } else {
        Write-Host "[3/3] Dashboard not found at $dashboard" -ForegroundColor Yellow
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  Demo complete! Results in: $($outputDir.FullName)" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor Cyan
Get-ChildItem $outputDir | ForEach-Object { Write-Host "  $_" }
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Explore the dashboard.html in your browser"
Write-Host "  2. Review report.md for a text summary"
if (-not $Live) {
    Write-Host "  3. Run .\scripts\demo.ps1 -Live for a real Foundry evaluation"
}
Write-Host ""
