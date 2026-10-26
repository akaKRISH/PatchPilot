"""Disposable workspace manager ensuring complete source repository isolation."""

import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from patchpilot.errors import OriginalRepositoryModifiedError, WorkspaceError
from patchpilot.safety.paths import PathPolicy
from patchpilot.schemas import PatchArtifact, RepositoryManifest
from patchpilot.workspace.diff import generate_workspace_diff
from patchpilot.workspace.manifest import compute_repository_manifest, verify_manifest_integrity


class WorkspaceManager:
    """Manages the creation, lifecycle, and integrity verification of isolated repair copies."""

    def __init__(self, source_repo_path: Path, data_dir: Path, run_id: str | None = None) -> None:
        self.source_repo = source_repo_path.resolve()
        if not self.source_repo.is_dir():
            raise WorkspaceError(f"Target repository path is not a directory: {self.source_repo}")

        self.data_dir = data_dir.resolve()
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:8]
        self.run_id = run_id or f"run_{timestamp}_{uid}"

        self.workspaces_root = self.data_dir / "workspaces"
        self.disposable_workspace = self.workspaces_root / self.run_id

        self.source_policy = PathPolicy(self.source_repo)
        self.disposable_policy: PathPolicy | None = None

        self.initial_manifest: RepositoryManifest | None = None
        self.modified_relative_files: set[str] = set()

    def setup(self) -> Path:
        """Snapshot the source repository and initialize the disposable working copy."""
        # 1. Compute initial manifest on source repository
        self.initial_manifest = compute_repository_manifest(self.source_repo, self.source_policy)

        # 2. Create isolated workspace directory
        self.disposable_workspace.mkdir(parents=True, exist_ok=True)
        self.disposable_policy = PathPolicy(self.disposable_workspace)

        # 3. Copy permitted files from source to disposable copy
        for rel_path, _entry in self.initial_manifest.entries.items():
            src_file = self.source_repo / rel_path
            dst_file = self.disposable_workspace / rel_path
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src_file, dst_file, follow_symlinks=False)
            except Exception as e:
                raise WorkspaceError(
                    f"Failed to copy file '{rel_path}' into disposable workspace: {e}"
                ) from e

        return self.disposable_workspace

    def mark_file_modified(self, relative_path: str) -> None:
        """Record that a relative path was modified in the disposable copy."""
        self.modified_relative_files.add(relative_path.replace("\\", "/"))

    def generate_patch(self) -> PatchArtifact:
        """Generate unified diff between original source and modified disposable copy."""
        if not self.modified_relative_files:
            return PatchArtifact(changed_files=[], unified_diff="")

        return generate_workspace_diff(
            original_dir=self.source_repo,
            modified_dir=self.disposable_workspace,
            changed_relative_paths=list(self.modified_relative_files),
        )

    def verify_source_integrity(self) -> tuple[bool, list[str]]:
        """Verify that the original source repository has not been modified."""
        if not self.initial_manifest:
            raise WorkspaceError("Cannot verify integrity: initial manifest was never captured.")

        is_identical, violations = verify_manifest_integrity(
            self.initial_manifest, self.source_repo, self.source_policy
        )
        if not is_identical:
            raise OriginalRepositoryModifiedError(
                "CRITICAL SAFETY VIOLATION: Source repository files were altered during repair!",
                details={"violations": violations},
            )
        return True, []

    def cleanup(self) -> None:
        """Remove the disposable workspace if needed."""
        if self.disposable_workspace.exists():
            shutil.rmtree(self.disposable_workspace, ignore_errors=True)
