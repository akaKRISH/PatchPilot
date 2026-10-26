"""Tool to read a file from the disposable workspace."""

from pathlib import Path
from typing import Any

from patchpilot.safety.paths import PathPolicy


def read_file(
    workspace_dir: Path,
    policy: PathPolicy,
    path: str,
    start_line: int | None = None,
    line_count: int | None = None,
) -> dict[str, Any]:
    """Read contents of a file inside the disposable workspace safely."""
    try:
        resolved = policy.sanitize_and_resolve(path, must_exist=True)
        if not resolved.is_file():
            return {"success": False, "error": f"Path '{path}' is not a regular file."}

        policy.validate_file_size(resolved)

        text = resolved.read_text(encoding="utf-8", errors="replace")
        all_lines = text.splitlines()
        total_lines = len(all_lines)

        s_line = max(1, start_line) if start_line is not None else 1
        count = min(max(1, line_count), 200) if line_count is not None else min(total_lines, 200)

        # 1-indexed to 0-indexed slice
        start_idx = s_line - 1
        end_idx = min(start_idx + count, total_lines)

        selected_lines = all_lines[start_idx:end_idx]
        formatted_lines = [
            f"{i:4d} | {line}" for i, line in enumerate(selected_lines, start=s_line)
        ]

        return {
            "success": True,
            "path": str(resolved.relative_to(workspace_dir)).replace("\\", "/"),
            "total_lines": total_lines,
            "start_line": s_line,
            "end_line": s_line + len(selected_lines) - 1 if selected_lines else s_line,
            "content": "\n".join(formatted_lines),
            "raw_content": "\n".join(selected_lines),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
