"""Agent orchestrator coordinating workspace isolation, baseline tests, repair, and reporting."""

import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from patchpilot.agent.repair_loop import RepairLoop
from patchpilot.config import PatchPilotConfig
from patchpilot.errors import OriginalRepositoryModifiedError, PatchPilotError
from patchpilot.ollama_client import OllamaClient
from patchpilot.safety.limits import ExecutionBudget
from patchpilot.schemas import (
    RepairStatus,
    RunReport,
    TaskRequest,
    TestSuiteResult,
    VerificationSummary,
)
from patchpilot.storage.run_store import RunStore
from patchpilot.tools.registry import ToolRegistry
from patchpilot.verification.baseline import run_baseline_tests
from patchpilot.verification.runner import TestRunner
from patchpilot.workspace.manager import WorkspaceManager

logger = logging.getLogger("patchpilot.orchestrator")


class AgentOrchestrator:
    """Coordinates end-to-end bug repair lifecycle with strict immutability checks."""

    def __init__(
        self,
        config: PatchPilotConfig,
        ollama_client: OllamaClient | None = None,
        test_runner: TestRunner | None = None,
        run_store: RunStore | None = None,
    ) -> None:
        self.config = config
        self.client = ollama_client or OllamaClient(config)
        self.runner = test_runner or TestRunner(config)
        self.store = run_store or RunStore(config.data_dir)

    def run_repair(self, task: TaskRequest) -> RunReport:
        """Execute full isolated repair pipeline."""
        start_time = datetime.now(UTC)
        start_mono = time.monotonic()

        repo_path = Path(task.repo_path).resolve()
        if not repo_path.is_dir():
            raise PatchPilotError(f"Target repository '{repo_path}' is not a valid directory.")

        workspace_mgr = WorkspaceManager(
            source_repo_path=repo_path,
            data_dir=self.config.data_dir,
        )
        run_id = workspace_mgr.run_id

        self.store.record_event(
            run_id=run_id,
            event_type="RUN_STARTED",
            payload={"task": task.model_dump(), "source_repo": str(repo_path)},
        )

        safety_violations: list[str] = []
        error_msg: str | None = None
        status = RepairStatus.UNRESOLVED

        # 1. Setup disposable workspace
        try:
            disposable_ws = workspace_mgr.setup()
        except Exception as e:
            logger.error(f"Failed setting up disposable workspace: {e}")
            return self._build_failure_report(
                run_id=run_id,
                task=task,
                status=RepairStatus.FAILED_SAFETY_CHECK,
                start_time=start_time,
                start_mono=start_mono,
                error_message=f"Workspace setup failed: {e}",
            )

        # 2. Run baseline test suite
        baseline_result: TestSuiteResult | None = None
        try:
            baseline_result = run_baseline_tests(
                runner=self.runner,
                workspace_dir=disposable_ws,
                suite=task.test_suite,
                target=task.test_target,
            )
            self.store.record_event(
                run_id=run_id,
                event_type="BASELINE_COMPLETED",
                payload={
                    "passed": baseline_result.passed,
                    "summary": baseline_result.summary,
                    "tests_run": baseline_result.tests_run,
                },
            )
        except Exception as e:
            logger.warning(f"Baseline test run could not be executed: {e}")
            error_msg = f"Baseline test execution note: {e}"

        # 3. Initialize tool registry and budget
        budget = ExecutionBudget(
            max_steps=self.config.max_agent_steps,
            max_tool_calls=self.config.max_tool_calls,
        )
        registry = ToolRegistry(
            workspace_dir=disposable_ws,
            policy=workspace_mgr.disposable_policy,  # type: ignore[arg-type]
            workspace_manager=workspace_mgr,
            test_runner=self.runner,
            budget=budget,
        )

        # 4. Execute repair loop
        repair_loop = RepairLoop(
            ollama_client=self.client,
            tool_registry=registry,
            task=task,
            config=self.config,
            baseline_result=baseline_result,
        )

        try:
            attempts, verification = repair_loop.run()
            if repair_loop.fatal_error and not error_msg:
                error_msg = repair_loop.fatal_error
        except Exception as e:
            logger.error(f"Repair loop execution error: {e}")
            error_msg = f"Repair loop error: {e}"
            attempts = []
            valid_baseline = (
                baseline_result if isinstance(baseline_result, TestSuiteResult) else None
            )
            verification = VerificationSummary(
                baseline_result=valid_baseline,
                final_result=None,
                is_regression_free=False,
                verified=False,
            )

        # 5. Verify source repository immutability
        original_unmodified = True
        try:
            workspace_mgr.verify_source_integrity()
        except OriginalRepositoryModifiedError as e:
            logger.critical(f"CRITICAL SAFETY VIOLATION: {e}")
            status = RepairStatus.FAILED_SAFETY_CHECK
            original_unmodified = False
            safety_violations.extend(e.details.get("violations", [str(e)]))

        # 6. Generate patch artifact
        patch_artifact = workspace_mgr.generate_patch()

        # 7. Determine final status
        if status != RepairStatus.FAILED_SAFETY_CHECK:
            if verification.verified:
                status = RepairStatus.FIXED
            elif verification.fixed_tests and not verification.regression_tests:
                status = RepairStatus.PARTIALLY_FIXED
            else:
                status = RepairStatus.UNRESOLVED

        duration = time.monotonic() - start_mono
        report = RunReport(
            run_id=run_id,
            task=task,
            status=status,
            start_time=start_time,
            end_time=datetime.now(UTC),
            duration_seconds=duration,
            attempts_made=len(attempts),
            max_attempts=self.config.max_repair_attempts,
            attempts=attempts,
            verification=verification,
            patch=patch_artifact,
            original_repo_unmodified=original_unmodified,
            safety_violations=safety_violations,
            error_message=error_msg,
        )

        self.store.save_run(report)
        return report

    def _build_failure_report(
        self,
        run_id: str,
        task: TaskRequest,
        status: RepairStatus,
        start_time: datetime,
        start_mono: float,
        error_message: str,
    ) -> RunReport:
        report = RunReport(
            run_id=run_id,
            task=task,
            status=status,
            start_time=start_time,
            end_time=datetime.now(UTC),
            duration_seconds=time.monotonic() - start_mono,
            attempts_made=0,
            max_attempts=self.config.max_repair_attempts,
            error_message=error_message,
        )
        self.store.save_run(report)
        return report
