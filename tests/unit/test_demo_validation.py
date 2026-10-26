"""Unit and regression tests for demo result verification and fail-closed reporting."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from patchpilot.agent.orchestrator import AgentOrchestrator
from patchpilot.config import PatchPilotConfig
from patchpilot.errors import OllamaResponseError
from patchpilot.schemas import (
    PatchArtifact,
    RepairStatus,
    RunReport,
    TaskRequest,
    TestCaseResult,
    TestSuiteName,
    TestSuiteResult,
    VerificationSummary,
)
from patchpilot.storage.run_store import RunStore


def test_unresolved_repair_cannot_produce_success_report(tmp_path: Path) -> None:
    """Verify that an UNRESOLVED report is rejected by validation logic."""
    store = RunStore(tmp_path)
    run_id = "run_test_unresolved"
    report = RunReport(
        run_id=run_id,
        task=TaskRequest(
            repo_path="repo", task_description="fix bug", test_suite=TestSuiteName.PYTEST
        ),
        status=RepairStatus.UNRESOLVED,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_seconds=10.0,
        attempts_made=1,
        max_attempts=3,
        verification=VerificationSummary(verified=False),
        original_repo_unmodified=True,
    )
    store.save_run(report)

    loaded = store.get_run(run_id)
    assert loaded is not None
    assert loaded.status != RepairStatus.FIXED
    assert loaded.verification is not None and loaded.verification.verified is False


def test_intact_original_file_does_not_imply_repair_success(tmp_path: Path) -> None:
    """Verify that an intact source repository alone does not qualify as repair success."""
    store = RunStore(tmp_path)
    run_id = "run_test_intact_only"
    report = RunReport(
        run_id=run_id,
        task=TaskRequest(
            repo_path="repo", task_description="fix bug", test_suite=TestSuiteName.PYTEST
        ),
        status=RepairStatus.UNRESOLVED,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_seconds=5.0,
        attempts_made=2,
        max_attempts=3,
        verification=VerificationSummary(verified=False, final_result=None),
        patch=PatchArtifact(changed_files=[], unified_diff=""),
        original_repo_unmodified=True,
    )
    store.save_run(report)

    loaded = store.get_run(run_id)
    assert loaded is not None
    # Intact original is True
    assert loaded.original_repo_unmodified is True
    # But repair status is NOT fixed
    assert loaded.status == RepairStatus.UNRESOLVED
    assert (loaded.verification and loaded.verification.verified) is False


def test_valid_repair_requires_evidence_from_current_run(tmp_path: Path) -> None:
    """Verify that older runs cannot be confused with current run."""
    store = RunStore(tmp_path)

    # Older successful run
    old_report = RunReport(
        run_id="run_old_fixed",
        task=TaskRequest(
            repo_path="repo", task_description="fix bug", test_suite=TestSuiteName.PYTEST
        ),
        status=RepairStatus.FIXED,
        start_time=datetime(2026, 1, 1, tzinfo=UTC),
        end_time=datetime(2026, 1, 1, tzinfo=UTC),
        duration_seconds=15.0,
        attempts_made=1,
        max_attempts=3,
        verification=VerificationSummary(
            verified=True,
            final_result=TestSuiteResult(
                suite_name=TestSuiteName.PYTEST,
                exit_code=0,
                passed=True,
                summary="1 passed",
                tests_passed=1,
                test_cases=[TestCaseResult(test_id="test_foo", passed=True)],
            ),
        ),
        original_repo_unmodified=True,
    )
    store.save_run(old_report)

    # Current run fails
    current_run_id = "run_current_failed"
    new_report = RunReport(
        run_id=current_run_id,
        task=TaskRequest(
            repo_path="repo", task_description="fix bug", test_suite=TestSuiteName.PYTEST
        ),
        status=RepairStatus.UNRESOLVED,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_seconds=2.0,
        attempts_made=1,
        max_attempts=3,
        verification=VerificationSummary(verified=False),
        original_repo_unmodified=True,
    )
    store.save_run(new_report)

    # Validating current run explicitly checks current_run_id
    current_loaded = store.get_run(current_run_id)
    assert current_loaded is not None
    assert current_loaded.status != RepairStatus.FIXED
    assert (current_loaded.verification and current_loaded.verification.verified) is False


def test_orchestrator_captures_provider_error_and_preserves_run_report(tmp_path: Path) -> None:
    """Verify that orchestrator captures persistent provider failure and writes UNRESOLVED report."""
    config = PatchPilotConfig(data_dir=tmp_path)
    store = RunStore(tmp_path)

    mock_client = MagicMock()
    mock_client.chat.side_effect = OllamaResponseError(
        "Ollama chat request failed with HTTP 500: model memory exhausted",
        status_code=500,
        response_body="model memory exhausted",
    )

    mock_runner = MagicMock()
    mock_runner.is_docker_available.return_value = False
    mock_runner.is_sandbox_image_available.return_value = False
    mock_runner.run_tests.return_value = TestSuiteResult(
        suite_name=TestSuiteName.PYTEST,
        exit_code=1,
        passed=False,
        summary="1 failed",
    )

    orchestrator = AgentOrchestrator(
        config=config,
        ollama_client=mock_client,
        test_runner=mock_runner,
        run_store=store,
    )

    # Create dummy source repo
    source_repo = tmp_path / "repo"
    source_repo.mkdir()
    (source_repo / "calc.py").write_text("def add(a, b): return a - b\n")

    task = TaskRequest(
        repo_path=str(source_repo),
        task_description="Fix add function",
        test_suite=TestSuiteName.PYTEST,
    )

    report = orchestrator.run_repair(task)

    assert report.status == RepairStatus.UNRESOLVED
    assert report.error_message is not None
    assert "HTTP 500" in report.error_message
    assert report.original_repo_unmodified is True

    # Report is saved on disk in run store
    saved_report = store.get_run(report.run_id)
    assert saved_report is not None
    assert saved_report.status == RepairStatus.UNRESOLVED


def test_orchestrator_reporting_consistency_applied_patches(tmp_path: Path) -> None:
    """Verify that successful edits appear consistently in attempt and run report."""
    from patchpilot.schemas import ToolCall

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    store = RunStore(data_dir)
    config = PatchPilotConfig(
        data_dir=data_dir,
        allow_host_execution=True,
        max_agent_steps=4,
        max_repair_attempts=1,
    )

    mock_client = MagicMock()
    mock_runner = MagicMock()

    # Baseline fails, final passes
    mock_runner.run_tests.side_effect = [
        TestSuiteResult(
            suite_name=TestSuiteName.PYTEST,
            exit_code=1,
            passed=False,
            summary="1 failed",
            test_cases=[TestCaseResult(test_id="test_calc", passed=False)],
        ),
        TestSuiteResult(
            suite_name=TestSuiteName.PYTEST,
            exit_code=0,
            passed=True,
            summary="1 passed",
            test_cases=[TestCaseResult(test_id="test_calc", passed=True)],
        ),
    ]

    # Model performs 1 failed edit, 1 successful edit, 1 run_tests
    mock_client.chat.side_effect = [
        {"message": {"role": "assistant", "content": "failed edit"}},
        {"message": {"role": "assistant", "content": "good edit"}},
        {"message": {"role": "assistant", "content": "run tests"}},
    ]
    mock_client.parse_tool_calls.side_effect = [
        [
            ToolCall(
                name="edit_file",
                arguments={
                    "path": "calc.py",
                    "old_text": "nonexistent",
                    "new_text": "replacement",
                },
            )
        ],
        [
            ToolCall(
                name="edit_file",
                arguments={
                    "path": "calc.py",
                    "old_text": "return a - b",
                    "new_text": "return a + b",
                },
            )
        ],
        [ToolCall(name="run_tests", arguments={"suite": "pytest"})],
    ]

    orchestrator = AgentOrchestrator(
        config=config,
        ollama_client=mock_client,
        test_runner=mock_runner,
        run_store=store,
    )

    source_repo = tmp_path / "source_repo"
    source_repo.mkdir()
    calc_file = source_repo / "calc.py"
    calc_file.write_text("def add(a, b):\n    return a - b\n")

    task = TaskRequest(
        repo_path=str(source_repo),
        task_description="Fix add",
        test_suite=TestSuiteName.PYTEST,
    )

    report = orchestrator.run_repair(task)

    assert report.status == RepairStatus.FIXED
    assert report.original_repo_unmodified is True
    # Verify original file untouched
    assert "return a - b" in calc_file.read_text()

    # Attempt applied_patches only has the 1 successful patch (not the failed one)
    assert len(report.attempts) == 1
    attempt = report.attempts[0]
    assert len(attempt.applied_patches) == 1
    assert attempt.applied_patches[0].relative_path == "calc.py"

    # Overall run report has consistent patch artifact
    assert report.patch is not None
    assert len(report.patch.changed_files) == 1
    assert report.patch.changed_files[0].relative_path == "calc.py"
    assert "return a + b" in report.patch.unified_diff
    assert "-    return a - b" in report.patch.unified_diff
    assert "+    return a + b" in report.patch.unified_diff
