# scripts/demo.ps1 — Generate mock results or run a live Foundry evaluation
# Usage:
#   .\scripts\demo.ps1
#   .\scripts\demo.ps1 -Live
#   .\scripts\demo.ps1 -Live -Resume
#   .\scripts\demo.ps1 -Live -Subscription <id> -ResourceGroup <rg> `
#       -ResourceName <name> -RouterDeployment <router> `
#       -BaselineDeployment <baseline> -JudgeDeployment <judge>

param(
    [switch]$Live,
    [switch]$Resume,
    [string]$Subscription,
    [string]$ResourceGroup,
    [string]$ResourceName,
    [string]$RouterDeployment,
    [string]$BaselineDeployment,
    [string]$JudgeDeployment
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$venvPip = Join-Path $projectRoot ".venv\Scripts\pip.exe"

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
        $requiredParameters = @{
            Subscription = $Subscription
            ResourceGroup = $ResourceGroup
            ResourceName = $ResourceName
            RouterDeployment = $RouterDeployment
            BaselineDeployment = $BaselineDeployment
            JudgeDeployment = $JudgeDeployment
        }
        $missingParameters = @(
            $requiredParameters.GetEnumerator() |
                Where-Object { [string]::IsNullOrWhiteSpace([string]$_.Value) } |
                ForEach-Object { "-$($_.Key)" }
        )
        if ($missingParameters.Count -gt 0) {
            throw "Live mode requires: $($missingParameters -join ', ')."
        }

        Write-Host "This calls real deployments and consumes billable tokens." -ForegroundColor Yellow
        Write-Host "  Router:   $RouterDeployment"
        Write-Host "  Baseline: $BaselineDeployment"
        Write-Host "  Judge:    $JudgeDeployment"
        Write-Host ""

        $az = Get-Command az -ErrorAction SilentlyContinue
        if (-not $az) {
            Write-Host "ERROR: Azure CLI is required for -Live." -ForegroundColor Red
            exit 1
        }

        Write-Host "[2/3] Running live 25-prompt evaluation..." -ForegroundColor Yellow
        az account set --subscription $Subscription
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to select Azure subscription $Subscription."
        }

        $accountKey = az cognitiveservices account keys list `
            --resource-group $ResourceGroup `
            --name $ResourceName `
            --query key1 `
            --output tsv
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($accountKey)) {
            throw "Unable to retrieve an access key for Foundry resource '$ResourceName'."
        }

        $resourceLocation = az cognitiveservices account show `
            --resource-group $ResourceGroup `
            --name $ResourceName `
            --query location `
            --output tsv
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($resourceLocation)) {
            throw "Unable to determine the Azure region for Foundry resource '$ResourceName'."
        }

        $endpoint = "https://$ResourceName.cognitiveservices.azure.com/"
        $env:AZURE_MODEL_ROUTER_ENDPOINT = $endpoint
        $env:AZURE_MODEL_ROUTER_KEY = $accountKey
        $env:AZURE_MODEL_ROUTER_DEPLOYMENT = $RouterDeployment
        $env:AZURE_OPENAI_ENDPOINT = $endpoint
        $env:AZURE_OPENAI_KEY = $accountKey
        $env:AZURE_BASELINE_DEPLOYMENT = $BaselineDeployment
        $env:AZURE_JUDGE_ENDPOINT = $endpoint
        $env:AZURE_JUDGE_KEY = $accountKey
        $env:AZURE_JUDGE_DEPLOYMENT = $JudgeDeployment
        $env:AZURE_PRICING_REGION = $resourceLocation

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
    $accountKey = $null
    Remove-Item Env:\AZURE_MODEL_ROUTER_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\AZURE_OPENAI_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\AZURE_JUDGE_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\AZURE_PRICING_REGION -ErrorAction SilentlyContinue
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
