# PatchPilot - Quality & Verification Check Script
$ErrorActionPreference = "Stop"

Write-Host "=== Running PatchPilot Quality Checks ===" -ForegroundColor Cyan

Write-Host "[1/4] Running Ruff Linter..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m ruff check src tests

Write-Host "[2/4] Running Ruff Formatter Check..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m ruff format --check src tests

Write-Host "[3/4] Running Mypy Type Checks..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m mypy src tests

Write-Host "[4/4] Running Pytest Unit & Security Test Suites..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m pytest tests/unit tests/security

Write-Host "=== All Quality Checks Passed! ===" -ForegroundColor Green
