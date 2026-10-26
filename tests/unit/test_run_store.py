"""Unit tests for RunStore persistence and event logging."""

from datetime import UTC, datetime
from pathlib import Path

from patchpilot.schemas import (
    FilePatchMetadata,
    PatchArtifact,
    RepairStatus,
    RunReport,
    TaskRequest,
    TestSuiteName,
)
from patchpilot.storage.run_store import RunStore


def test_save_and_retrieve_run(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    now = datetime.now(UTC)

    report = RunReport(
        run_id="run_test_123",
        task=TaskRequest(
            repo_path=str(tmp_path),
            task_description="Fix test bug",
            test_suite=TestSuiteName.PYTEST,
        ),
        status=RepairStatus.FIXED,
        start_time=now,
        end_time=now,
        duration_seconds=3.5,
        attempts_made=1,
        max_attempts=3,
        patch=PatchArtifact(
            changed_files=[
                FilePatchMetadata(
                    relative_path="calc.py",
                    before_sha256="abc",
                    after_sha256="def",
                    lines_added=1,
                    lines_removed=1,
                )
            ],
            unified_diff="--- a/calc.py\n+++ b/calc.py\n@@ -1 +1 @@\n-old\n+new",
        ),
    )

    path = store.save_run(report)
    assert path.is_file()

    # Verify separate .patch file created
    patch_file = tmp_path / "runs" / "run_test_123.patch"
    assert patch_file.is_file()
    assert "+new" in patch_file.read_text(encoding="utf-8")

    # Load back
    loaded = store.get_run("run_test_123")
    assert loaded is not None
    assert loaded.status == RepairStatus.FIXED

    # List runs
    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run_test_123"

    # Event log exists
    assert store.events_log.is_file()
