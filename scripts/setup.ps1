# PatchPilot - Windows Setup Script
# Stop on errors
$ErrorActionPreference = "Stop"

Write-Host "=== PatchPilot Setup ===" -ForegroundColor Cyan

# Check Python
if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed or not in PATH."
}

# Create local .venv if not present
if (-not (Test-Path ".venv")) {
    Write-Host "Creating local virtual environment (.venv)..." -ForegroundColor Yellow
    py -3.13 -m venv .venv
}

Write-Host "Upgrading pip..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "Installing PatchPilot and dev dependencies in editable mode..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Write-Host "Running Doctor diagnostics..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m patchpilot doctor

Write-Host "=== Setup Complete! ===" -ForegroundColor Green
