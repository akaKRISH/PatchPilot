"""Tool to apply surgical, exact-match text edits to files in the disposable workspace."""

from pathlib import Path
from typing import Any

from patchpilot.safety.paths import PathPolicy
from patchpilot.workspace.manager import WorkspaceManager
from patchpilot.workspace.manifest import hash_file_sha256


def edit_file(
    workspace_dir: Path,
    policy: PathPolicy,
    workspace_manager: WorkspaceManager,
    path: str,
    old_text: str,
    new_text: str,
) -> dict[str, Any]:
    """Replace exact occurrences of old_text with new_text in the target file."""
    try:
        resolved = policy.sanitize_and_resolve(path, must_exist=True)
        if not resolved.is_file():
            return {"success": False, "error": f"Target path '{path}' is not a regular file."}

        policy.validate_file_size(resolved)

        content = resolved.read_text(encoding="utf-8")
        before_sha = hash_file_sha256(resolved)

        # Check occurrence count
        count = content.count(old_text)
        if count == 0:
            return {
                "success": False,
                "error": f"Target old_text was not found in '{path}'. Please ensure exact whitespace and content.",
            }
        elif count > 1:
            return {
                "success": False,
                "error": (
                    f"Ambiguous replacement in '{path}': target old_text occurs {count} times. "
                    "Provide more surrounding context to disambiguate."
                ),
            }

        # Apply single exact replacement
        new_content = content.replace(old_text, new_text, 1)
        resolved.write_text(new_content, encoding="utf-8")
        after_sha = hash_file_sha256(resolved)

        rel_path = str(resolved.relative_to(workspace_dir)).replace("\\", "/")
        workspace_manager.mark_file_modified(rel_path)

        old_lines = old_text.count("\n") + 1
        new_lines = new_text.count("\n") + 1

        return {
            "success": True,
            "path": rel_path,
            "relative_path": rel_path,
            "before_sha256": before_sha,
            "after_sha256": after_sha,
            "lines_removed": old_lines,
            "lines_added": new_lines,
            "message": f"Successfully updated '{rel_path}'.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
