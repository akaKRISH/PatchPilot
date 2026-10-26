"""Unit tests for workspace manager and integrity verification."""

from pathlib import Path

import pytest

from patchpilot.errors import OriginalRepositoryModifiedError
from patchpilot.workspace.manager import WorkspaceManager


def test_workspace_isolation_and_immutability(temp_repo: Path, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    mgr = WorkspaceManager(source_repo_path=temp_repo, data_dir=data_dir)
    ws = mgr.setup()

    assert ws.exists()
    assert (ws / "calculator.py").exists()

    # Verify source integrity passes initially
    ok, violations = mgr.verify_source_integrity()
    assert ok is True
    assert len(violations) == 0

    # Modify disposable workspace
    (ws / "calculator.py").write_text("modified", encoding="utf-8")
    mgr.mark_file_modified("calculator.py")

    # Original repository MUST still be untouched!
    ok, violations = mgr.verify_source_integrity()
    assert ok is True

    # If original repository is tampered with, must raise error
    (temp_repo / "tampered.txt").write_text("leak", encoding="utf-8")
    with pytest.raises(OriginalRepositoryModifiedError):
        mgr.verify_source_integrity()
