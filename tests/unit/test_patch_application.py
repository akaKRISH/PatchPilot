"""Unit tests for patch application and surgical file editing."""

from pathlib import Path

from patchpilot.schemas import FilePatchMetadata
from patchpilot.tools.edit_file import edit_file
from patchpilot.workspace.manager import WorkspaceManager


def test_unique_exact_replacement(workspace_manager: WorkspaceManager) -> None:
    ws = workspace_manager.disposable_workspace
    policy = workspace_manager.disposable_policy
    assert policy is not None

    res = edit_file(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=workspace_manager,
        path="calculator.py",
        old_text="def add(a, b):\n    return a - b",
        new_text="def add(a, b):\n    return a + b",
    )
    assert res["success"] is True
    assert res["path"] == "calculator.py"
    assert res["relative_path"] == "calculator.py"
    assert res["before_sha256"] != res["after_sha256"]
    assert res["lines_removed"] == 2
    assert res["lines_added"] == 2
    assert "calculator.py" in workspace_manager.modified_relative_files

    patch_meta = FilePatchMetadata.model_validate(res)
    assert patch_meta.relative_path == "calculator.py"
    assert patch_meta.lines_added == 2
    assert patch_meta.lines_removed == 2

    content = (ws / "calculator.py").read_text(encoding="utf-8")
    assert "return a + b" in content


def test_target_text_not_found(workspace_manager: WorkspaceManager) -> None:
    ws = workspace_manager.disposable_workspace
    policy = workspace_manager.disposable_policy
    assert policy is not None

    res = edit_file(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=workspace_manager,
        path="calculator.py",
        old_text="nonexistent function text",
        new_text="replacement",
    )
    assert res["success"] is False
    assert "not found" in res["error"]
    assert "calculator.py" not in workspace_manager.modified_relative_files


def test_ambiguous_replacement_rejected(
    tmp_path: Path, workspace_manager: WorkspaceManager
) -> None:
    ws = workspace_manager.disposable_workspace
    policy = workspace_manager.disposable_policy
    assert policy is not None

    dup_file = ws / "duplicates.txt"
    dup_file.write_text("hello\nworld\nhello\n", encoding="utf-8")

    res = edit_file(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=workspace_manager,
        path="duplicates.txt",
        old_text="hello",
        new_text="greetings",
    )
    assert res["success"] is False
    assert "Ambiguous replacement" in res["error"]
    assert "duplicates.txt" not in workspace_manager.modified_relative_files
