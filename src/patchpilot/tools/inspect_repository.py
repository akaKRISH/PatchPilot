"""Tool to inspect repository structure and files safely."""

from pathlib import Path
from typing import Any

from patchpilot.safety.paths import PathPolicy


def inspect_repository(
    workspace_dir: Path,
    policy: PathPolicy,
    subpath: str | None = None,
) -> dict[str, Any]:
    """Return a bounded inventory of repository files and directories."""
    target_dir = workspace_dir
    if subpath:
        target_dir = policy.sanitize_and_resolve(subpath, must_exist=True)
        if not target_dir.is_dir():
            return {
                "success": False,
                "error": f"Specified subpath '{subpath}' is not a directory.",
            }

    files: list[str] = []
    directories: list[str] = []

    for item in sorted(target_dir.rglob("*")):
        if policy.is_secret_or_excluded(item):
            continue

        try:
            rel = str(item.relative_to(workspace_dir)).replace("\\", "/")
            if item.is_dir():
                directories.append(rel)
            elif item.is_file():
                files.append(rel)
        except Exception:
            continue

        # Cap total items to prevent massive context bloat
        if len(files) + len(directories) >= 200:
            break

    return {
        "success": True,
        "root": str(workspace_dir.name),
        "total_files": len(files),
        "total_directories": len(directories),
        "files": files[:150],
        "directories": directories[:50],
    }
