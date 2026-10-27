# PatchPilot - Windows Setup Script
# Stop on unhandled script errors
$ErrorActionPreference = "Stop"

Write-Host "=== PatchPilot Setup ===" -ForegroundColor Cyan

# 1. Virtual Environment Setup
$venvPython = Join-Path ".venv" "Scripts\python.exe"
if (Test-Path $venvPython) {
    Write-Host "`n[1/5] Using existing virtual environment (.venv)..." -ForegroundColor Green
} else {
    Write-Host "`n[1/5] Detecting supported Python runtime (3.11, 3.12, 3.13)..." -ForegroundColor Cyan
    $selectedPythonCmd = $null

    # Test py launcher with specific versions first
    foreach ($ver in @("-3.13", "-3.12", "-3.11")) {
        try {
            $check = & py $ver -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($check -match "^3\.(11|12|13)$") {
                $selectedPythonCmd = @("py", $ver)
                Write-Host "Found Python $check via py $ver" -ForegroundColor Green
                break
            }
        } catch {}
    }

    # If not found via py -X, test default 'python' and 'py'
    if (-not $selectedPythonCmd) {
        foreach ($cmd in @("python", "py")) {
            try {
                $check = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($check -match "^3\.(11|12|13)$") {
                    $selectedPythonCmd = @($cmd)
                    Write-Host "Found Python $check via $cmd" -ForegroundColor Green
                    break
                }
            } catch {}
        }
    }

    if (-not $selectedPythonCmd) {
        Write-Error "ABORTING SETUP: No supported Python version (3.11, 3.12, or 3.13) found. Please install Python 3.11, 3.12, or 3.13."
        exit 1
    }

    Write-Host "Creating virtual environment in .venv..." -ForegroundColor Yellow
    & $selectedPythonCmd[0] ($selectedPythonCmd[1..($selectedPythonCmd.Length-1)] + @("-m", "venv", ".venv"))
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
}

# 2. Install Dependencies
Write-Host "`n[2/5] Installing PatchPilot and developer dependencies..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to upgrade pip."
    exit 1
}

& $venvPython -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install PatchPilot dependencies."
    exit 1
}
Write-Host "PatchPilot package installed in editable mode." -ForegroundColor Green

# 3. Check Ollama & Model
Write-Host "`n[3/5] Checking Ollama service and default model..." -ForegroundColor Cyan
$ollamaReachable = $false
$modelInstalled = $false

$ollamaCheck = & $venvPython -c "
from patchpilot.config import PatchPilotConfig
from patchpilot.ollama_client import OllamaClient
cfg = PatchPilotConfig.load()
client = OllamaClient(cfg)
reachable = client.is_reachable()
installed = client.is_model_installed(cfg.model_name) if reachable else False
print(f'REACHABLE={reachable}')
print(f'INSTALLED={installed}')
print(f'MODEL={cfg.model_name}')
" 2>$null

if ($ollamaCheck -match "REACHABLE=True") {
    $ollamaReachable = $true
    Write-Host "Ollama server is online and reachable." -ForegroundColor Green
} else {
    Write-Host "Ollama server is not running or unreachable." -ForegroundColor Yellow
    Write-Host "  To start Ollama, run: ollama serve" -ForegroundColor Gray
}

if ($ollamaCheck -match "INSTALLED=True") {
    $modelInstalled = $true
    Write-Host "Target model 'qwen3.5:4b' is installed." -ForegroundColor Green
} else {
    Write-Host "Target model 'qwen3.5:4b' is not installed." -ForegroundColor Yellow
    Write-Host "  To install the model, run: ollama pull qwen3.5:4b" -ForegroundColor Cyan
}

# 4. Check Docker & Sandbox Image
Write-Host "`n[4/5] Checking Docker sandbox..." -ForegroundColor Cyan
$dockerRunning = $false
$imageBuilt = $false

$dockerCheck = & $venvPython -c "
from patchpilot.config import PatchPilotConfig
from patchpilot.verification.runner import TestRunner
cfg = PatchPilotConfig.load()
runner = TestRunner(cfg)
avail = runner.is_docker_available()
img = runner.is_sandbox_image_available() if avail else False
print(f'DOCKER={avail}')
print(f'IMAGE={img}')
print(f'IMAGE_NAME={runner.docker_image}')
" 2>$null

if ($dockerCheck -match "DOCKER=True") {
    $dockerRunning = $true
    Write-Host "Docker daemon is reachable." -ForegroundColor Green

    if ($dockerCheck -match "IMAGE=True") {
        $imageBuilt = $true
        Write-Host "Sandbox image 'patchpilot-sandbox:latest' is ready." -ForegroundColor Green
    } else {
        Write-Host "Building sandbox image 'patchpilot-sandbox:latest'..." -ForegroundColor Yellow
        docker build -t patchpilot-sandbox:latest .\sandbox\
        if ($LASTEXITCODE -eq 0) {
            $imageBuilt = $true
            Write-Host "Sandbox image built successfully." -ForegroundColor Green
        } else {
            Write-Host "Failed to build sandbox image automatically." -ForegroundColor Red
        }
    }
} else {
    Write-Host "Docker daemon is not running. Sandbox image cannot be checked or built yet." -ForegroundColor Yellow
    Write-Host "  Start Docker Desktop and verify with: docker info" -ForegroundColor Gray
}

# 5. Doctor diagnostics & Summary
Write-Host "`n[5/5] Running PatchPilot diagnostics..." -ForegroundColor Cyan
$doctorExitCode = 0
try {
    & $venvPython -m patchpilot doctor
    $doctorExitCode = $LASTEXITCODE
} catch {
    $doctorExitCode = 1
}

Write-Host "`n========================================================" -ForegroundColor Cyan
if ($doctorExitCode -eq 0 -and $ollamaReachable -and $modelInstalled -and $dockerRunning -and $imageBuilt) {
    Write-Host " SETUP COMPLETE: Environment is fully ready for safe repairs!" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "Try running the demo:" -ForegroundColor Green
    Write-Host "  .\.venv\Scripts\python.exe -m patchpilot demo" -ForegroundColor White
} else {
    Write-Host " PACKAGE SETUP COMPLETE (Action Required for Full Repair Readiness)" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "The Python environment and dependencies are installed successfully." -ForegroundColor Yellow
    Write-Host "However, safe sandboxed repairs require the following remaining steps:" -ForegroundColor Yellow

    if (-not $ollamaReachable) {
        Write-Host "  - Start Ollama: Launch Ollama Desktop or run 'ollama serve'" -ForegroundColor Cyan
    }
    if (-not $modelInstalled) {
        Write-Host "  - Pull the model: ollama pull qwen3.5:4b" -ForegroundColor Cyan
    }
    if (-not $dockerRunning) {
        Write-Host "  - Start Docker Desktop and verify with: docker info" -ForegroundColor Cyan
        Write-Host "  - Build sandbox image: docker build -t patchpilot-sandbox:latest .\sandbox\" -ForegroundColor Cyan
    } elseif (-not $imageBuilt) {
        Write-Host "  - Build sandbox image: docker build -t patchpilot-sandbox:latest .\sandbox\" -ForegroundColor Cyan
    }
    Write-Host "`nVerify readiness anytime with:" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\python.exe -m patchpilot doctor" -ForegroundColor White
}
Write-Host "========================================================`n" -ForegroundColor Cyan
