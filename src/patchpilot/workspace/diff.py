"""Unified diff generation between original and modified workspaces."""

import difflib
from pathlib import Path

from patchpilot.schemas import FilePatchMetadata, PatchArtifact
from patchpilot.workspace.manifest import hash_file_sha256


def generate_workspace_diff(
    original_dir: Path,
    modified_dir: Path,
    changed_relative_paths: list[str],
) -> PatchArtifact:
    """Generate a clean unified diff and metadata for specified changed files."""
    diff_chunks: list[str] = []
    patch_metadatas: list[FilePatchMetadata] = []

    for rel_str in sorted(changed_relative_paths):
        orig_file = (original_dir / rel_str).resolve()
        mod_file = (modified_dir / rel_str).resolve()

        orig_lines: list[str] = []
        before_sha = "0000000000000000000000000000000000000000000000000000000000000000"
        if orig_file.is_file():
            before_sha = hash_file_sha256(orig_file)
            try:
                orig_lines = orig_file.read_text(encoding="utf-8", errors="replace").splitlines(
                    keepends=True
                )
            except Exception:
                orig_lines = []

        mod_lines: list[str] = []
        after_sha = "0000000000000000000000000000000000000000000000000000000000000000"
        if mod_file.is_file():
            after_sha = hash_file_sha256(mod_file)
            try:
                mod_lines = mod_file.read_text(encoding="utf-8", errors="replace").splitlines(
                    keepends=True
                )
            except Exception:
                mod_lines = []

        # Generate unified diff
        diff_iter = difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile=f"a/{rel_str}",
            tofile=f"b/{rel_str}",
        )
        diff_text = "".join(diff_iter)
        if diff_text:
            diff_chunks.append(diff_text)

        # Count added and removed lines
        added = sum(
            1
            for line in diff_text.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        removed = sum(
            1
            for line in diff_text.splitlines()
            if line.startswith("-") and not line.startswith("---")
        )

        patch_metadatas.append(
            FilePatchMetadata(
                relative_path=rel_str,
                before_sha256=before_sha,
                after_sha256=after_sha,
                lines_added=added,
                lines_removed=removed,
            )
        )

    full_unified_diff = "\n".join(diff_chunks)
    return PatchArtifact(
        changed_files=patch_metadatas,
        unified_diff=full_unified_diff,
    )
