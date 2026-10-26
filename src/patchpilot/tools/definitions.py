"""Tool definitions in Ollama function schema format."""

from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "inspect_repository",
            "description": "Get an inventory of repository files, directories, and project structure. Automatically excludes secrets, git, and virtual environments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subpath": {
                        "type": "string",
                        "description": "Optional relative subdirectory to inspect. Defaults to workspace root.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search text files in the workspace for an exact string, identifier, or regex pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The text or identifier to search for in files.",
                    },
                    "path_filter": {
                        "type": "string",
                        "description": "Optional relative subpath or file extension filter (e.g. '.py' or 'tests').",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of matching lines to return (capped at 50).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file in the disposable workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file to read.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Optional 1-based start line number to view.",
                    },
                    "line_count": {
                        "type": "integer",
                        "description": "Optional number of lines to read (capped at 200).",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Apply a precise, surgical edit to a file in the disposable workspace by replacing target text with replacement text. Fails safely if target text matches ambiguously or is not found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path of the file to edit.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Exact text sequence to be replaced. Must be unique in the file.",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text to substitute for old_text.",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the approved test suite on the disposable workspace to verify behavior and detect regressions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "suite": {
                        "type": "string",
                        "enum": [
                            "pytest",
                            "unittest",
                            "compileall",
                            "jest",
                            "go_test",
                            "cargo_test",
                        ],
                        "description": "Predefined test suite name to execute.",
                    },
                    "target": {
                        "type": "string",
                        "description": "Optional targeted test file or directory path relative to workspace.",
                    },
                },
                "required": ["suite"],
            },
        },
    },
]


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return copies of all registered Ollama tool definitions."""
    return [dict(t) for t in TOOL_DEFINITIONS]
