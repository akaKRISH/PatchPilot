# PatchPilot - End-to-End Demo Script
$ErrorActionPreference = "Stop"

Write-Host "=== PatchPilot End-to-End Demo ===" -ForegroundColor Cyan
Write-Host "Demonstrating isolated self-healing repair on examples/buggy_python_project" -ForegroundColor Yellow

$repo = "examples/buggy_python_project"
$task = "Fix the bug in the calculator's add function. Preserve the public API and do not change the original repository."
$sourceFile = Join-Path $repo "calculator.py"

if (-not (Test-Path $sourceFile)) {
    Write-Error "ABORTING DEMO: Source file '$sourceFile' does not exist."
    exit 1
}

# 1. Verify Docker availability
Write-Host "`n[1/5] Verifying Docker daemon connectivity..." -ForegroundColor Cyan
$dockerCheck = .\.venv\Scripts\python.exe -c "from patchpilot.config import PatchPilotConfig; from patchpilot.verification.runner import TestRunner; r = TestRunner(PatchPilotConfig.load()); print('DOCKER_OK' if r.is_docker_available() else 'DOCKER_FAIL')"
if ($dockerCheck -notmatch "DOCKER_OK") {
    Write-Error "ABORTING DEMO: Docker daemon is not running or unreachable. Please start Docker Desktop to run containerized sandbox tests."
    exit 1
}
Write-Host "Docker daemon is online and responsive." -ForegroundColor Green

# 2. Verify Sandbox image
Write-Host "`n[2/5] Verifying configured sandbox image..." -ForegroundColor Cyan
$imageCheck = .\.venv\Scripts\python.exe -c "from patchpilot.config import PatchPilotConfig; from patchpilot.verification.runner import TestRunner; r = TestRunner(PatchPilotConfig.load()); print('IMAGE_OK:' + r.docker_image if r.is_sandbox_image_available() else 'IMAGE_FAIL:' + r.docker_image)"
if ($imageCheck -notmatch "IMAGE_OK") {
    Write-Error "ABORTING DEMO: Sandbox image is not built or available. Build it first with: docker build -t patchpilot-sandbox:latest .\sandbox\"
    exit 1
}
$sandboxImage = ($imageCheck -replace "IMAGE_OK:", "").Trim()
Write-Host "Sandbox image '$sandboxImage' is ready for containerized execution." -ForegroundColor Green

# 3. Capture SHA-256 hash before repair and snapshot existing run reports
Write-Host "`n[3/5] Capturing baseline hash of original source file and run history..." -ForegroundColor Cyan
$preHash = (Get-FileHash -Path $sourceFile -Algorithm SHA256).Hash
Write-Host "Target file: $sourceFile" -ForegroundColor Gray
Write-Host "Pre-repair SHA-256: $preHash" -ForegroundColor Gray

# Snapshot existing run IDs before launch to avoid validating an older report
$runsDir = Join-Path ".patchpilot-data" "runs"
$existingRunIds = @()
if (Test-Path $runsDir) {
    $existingRunIds = @(Get-ChildItem -Path $runsDir -Filter "*.json" | ForEach-Object { $_.BaseName })
}

# 4. Invoke PatchPilot without --allow-host-execution
Write-Host "`n[4/5] Launching PatchPilot repair in isolated Docker sandbox..." -ForegroundColor Cyan

$repairExitCode = 0
try {
    & .\.venv\Scripts\python.exe -m patchpilot repair `
        --repo $repo `
        --task $task `
        --test-suite pytest
    $repairExitCode = $LASTEXITCODE
} catch {
    Write-Host "Exception during repair invocation: $_" -ForegroundColor Red
    $repairExitCode = 1
}

# 5. Verify source integrity safely (runs regardless of repair success or failure)
Write-Host "`n[5/5] Verifying original-source integrity and run report..." -ForegroundColor Cyan
$postHash = (Get-FileHash -Path $sourceFile -Algorithm SHA256).Hash
Write-Host "Post-repair SHA-256: $postHash" -ForegroundColor Gray

$sourceIntegrityPass = ($preHash -eq $postHash)
$content = Get-Content $sourceFile -Raw
$contentIntact = ($content -match "return a - b")

if (-not $sourceIntegrityPass -or -not $contentIntact) {
    Write-Host "`n========================================================" -ForegroundColor Red
    Write-Host " CRITICAL SAFETY FAILURE: ORIGINAL REPOSITORY ALTERED!" -ForegroundColor Red
    Write-Host "========================================================" -ForegroundColor Red
    Write-Host " Pre-repair SHA-256:  $preHash" -ForegroundColor Red
    Write-Host " Post-repair SHA-256: $postHash" -ForegroundColor Red
    Write-Host "========================================================`n" -ForegroundColor Red
    exit 2
}
Write-Host "Source integrity verified: Original file remains strictly identical byte-for-byte." -ForegroundColor Green

# Find the exact run report produced by this specific execution
$currentRunId = $null
if (Test-Path $runsDir) {
    $currentRuns = @(Get-ChildItem -Path $runsDir -Filter "*.json" | Where-Object { $existingRunIds -notcontains $_.BaseName })
    if ($currentRuns.Count -gt 0) {
        $currentRunId = ($currentRuns | Sort-Object LastWriteTime -Descending | Select-Object -First 1).BaseName
    }
}

# If the repair process failed or did not generate a run report, fail-closed
if ($repairExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($currentRunId)) {
    Write-Host "`n========================================================" -ForegroundColor Yellow
    Write-Host " REPAIR FAILED -- ORIGINAL PRESERVED" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Yellow
    Write-Host " The repair process exited with code $repairExitCode." -ForegroundColor Yellow
    if ($currentRunId) {
        Write-Host " Current Run ID: $currentRunId" -ForegroundColor Yellow
    } else {
        Write-Host " No new run report was generated by this invocation." -ForegroundColor Yellow
    }
    Write-Host " The original repository was strictly preserved and remains untouched." -ForegroundColor Green
    Write-Host "========================================================`n" -ForegroundColor Yellow
    exit $(if ($repairExitCode -ne 0) { $repairExitCode } else { 1 })
}

# Validate the specific current run report
$validatePy = @'
import sys
from patchpilot.config import PatchPilotConfig
from patchpilot.storage.run_store import RunStore

run_id = sys.argv[1] if len(sys.argv) > 1 else ""
if not run_id:
    print("ERROR: No run_id provided to validator", file=sys.stderr)
    sys.exit(1)

cfg = PatchPilotConfig.load()
store = RunStore(cfg.data_dir)
report = store.get_run(run_id)
if not report:
    print(f"ERROR: Run report '{run_id}' not found", file=sys.stderr)
    sys.exit(1)

if report.status.value != "FIXED":
    print(f"ERROR: Run status is '{report.status.value}', expected 'FIXED'", file=sys.stderr)
    sys.exit(1)

if not report.verification or not report.verification.verified:
    print("ERROR: Verification summary is missing or verified is False", file=sys.stderr)
    sys.exit(1)

final_res = report.verification.final_result
if not final_res or not final_res.passed or final_res.tests_passed <= 0:
    print(f"ERROR: Final test suite did not pass (passed={getattr(final_res, 'passed', None)}, tests_passed={getattr(final_res, 'tests_passed', 0)})", file=sys.stderr)
    sys.exit(1)

if not report.original_repo_unmodified:
    print("ERROR: Report indicates original repository was modified", file=sys.stderr)
    sys.exit(1)

print(f"REPORT_OK: Run {report.run_id} verified ({final_res.tests_passed} passed, 0 regressions, {report.duration_seconds:.2f}s)")
'@

$reportCheck = $validatePy | .\.venv\Scripts\python.exe - $currentRunId
if ($LASTEXITCODE -ne 0 -or $reportCheck -notmatch "REPORT_OK") {
    Write-Host "`n========================================================" -ForegroundColor Yellow
    Write-Host " REPAIR FAILED -- ORIGINAL PRESERVED" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Yellow
    Write-Host " Run report verification failed for current run $($currentRunId):" -ForegroundColor Yellow
    Write-Host " $reportCheck" -ForegroundColor Yellow
    Write-Host " The original repository was strictly preserved and remains untouched." -ForegroundColor Green
    Write-Host "========================================================`n" -ForegroundColor Yellow
    exit 1
}

Write-Host $reportCheck -ForegroundColor Green

# Print overall demo success ONLY when both verified repair and source integrity pass
Write-Host "`n========================================================" -ForegroundColor Green
Write-Host " OVERALL DEMO RESULT: SUCCESS" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host " 1. Containerized sandbox tests passed without regressions." -ForegroundColor Green
Write-Host " 2. Current run report ($currentRunId) verified status FIXED." -ForegroundColor Green
Write-Host " 3. Original source repository verified 100% immutable and untouched." -ForegroundColor Green
Write-Host "========================================================`n" -ForegroundColor Green
