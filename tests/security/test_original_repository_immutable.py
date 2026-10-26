"""Security tests verifying that original repositories remain strictly immutable."""

from pathlib import Path

import pytest

from patchpilot.config import PatchPilotConfig
from patchpilot.schemas import ToolCall
from patchpilot.tools.registry import ToolRegistry
from patchpilot.verification.runner import TestRunner
from patchpilot.workspace.manager import WorkspaceManager
from patchpilot.workspace.manifest import hash_file_sha256


@pytest.mark.security
def test_original_repository_remains_strictly_immutable(
    temp_repo: Path,
    test_config: PatchPilotConfig,
) -> None:
    original_calc = temp_repo / "calculator.py"
    original_hash_before = hash_file_sha256(original_calc)
    original_content_before = original_calc.read_text(encoding="utf-8")

    mgr = WorkspaceManager(source_repo_path=temp_repo, data_dir=test_config.data_dir)
    ws = mgr.setup()
    policy = mgr.disposable_policy
    assert policy is not None

    from patchpilot.safety.limits import ExecutionBudget

    runner = TestRunner(test_config)
    registry = ToolRegistry(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=mgr,
        test_runner=runner,
        budget=ExecutionBudget(),
    )

    # Apply edit to disposable copy
    edit_call = ToolCall(
        name="edit_file",
        arguments={
            "path": "calculator.py",
            "old_text": "def add(a, b):\n    return a - b",
            "new_text": "def add(a, b):\n    return a + b",
        },
    )
    edit_res = registry.execute(edit_call)
    assert edit_res.success is True

    # Check disposable copy has new content
    disposable_calc = ws / "calculator.py"
    assert "return a + b" in disposable_calc.read_text(encoding="utf-8")

    # CRITICAL CHECK: Original repository content and hash MUST be 100% unchanged!
    original_hash_after = hash_file_sha256(original_calc)
    original_content_after = original_calc.read_text(encoding="utf-8")

    assert original_hash_before == original_hash_after
    assert original_content_before == original_content_after

    # Formal integrity verification passes
    is_identical, violations = mgr.verify_source_integrity()
    assert is_identical is True
    assert len(violations) == 0
