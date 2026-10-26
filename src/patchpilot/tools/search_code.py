"""Tool to search code in workspace files."""

from pathlib import Path
from typing import Any

from patchpilot.safety.paths import PathPolicy


def search_code(
    workspace_dir: Path,
    policy: PathPolicy,
    query: str,
    path_filter: str | None = None,
    max_results: int = 30,
) -> dict[str, Any]:
    """Search text files for matches to the specified query."""
    if not query or not query.strip():
        return {"success": False, "error": "Search query cannot be empty."}

    max_results = min(max(1, max_results), 50)
    matches: list[dict[str, Any]] = []

    for path in sorted(workspace_dir.rglob("*")):
        if not path.is_file():
            continue
        if policy.is_secret_or_excluded(path):
            continue

        rel_path = str(path.relative_to(workspace_dir)).replace("\\", "/")

        if path_filter and path_filter not in rel_path:
            continue

        # Skip files exceeding safety size
        if path.stat().st_size > policy.max_file_bytes:
            continue

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line_idx, line in enumerate(f, start=1):
                    if query in line:
                        matches.append(
                            {
                                "file": rel_path,
                                "line": line_idx,
                                "content": line.rstrip()[:200],  # Bound line length
                            }
                        )
                        if len(matches) >= max_results:
                            break
        except Exception:
            continue

        if len(matches) >= max_results:
            break

    return {
        "success": True,
        "query": query,
        "match_count": len(matches),
        "matches": matches,
    }
