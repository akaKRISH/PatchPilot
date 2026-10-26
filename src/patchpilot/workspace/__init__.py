"""Workspace management module for PatchPilot."""

from patchpilot.workspace.diff import generate_workspace_diff
from patchpilot.workspace.manager import WorkspaceManager
from patchpilot.workspace.manifest import compute_repository_manifest, verify_manifest_integrity

__all__ = [
    "WorkspaceManager",
    "compute_repository_manifest",
    "generate_workspace_diff",
    "verify_manifest_integrity",
]
