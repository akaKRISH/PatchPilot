"""Explicit tool registry with budget limits, argument validation, and execution tracking."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from patchpilot.errors import BudgetExceededError, ToolArgumentError
from patchpilot.safety.limits import ExecutionBudget
from patchpilot.safety.paths import PathPolicy
from patchpilot.schemas import ToolCall, ToolResult
from patchpilot.tools.definitions import get_tool_definitions
from patchpilot.tools.edit_file import edit_file
from patchpilot.tools.inspect_repository import inspect_repository
from patchpilot.tools.read_file import read_file
from patchpilot.tools.run_tests import run_tests_tool
from patchpilot.tools.search_code import search_code
from patchpilot.verification.runner import TestRunner
from patchpilot.workspace.manager import WorkspaceManager


class ToolRegistry:
    """Manages and executes registered tools against an isolated workspace."""

    def __init__(
        self,
        workspace_dir: Path,
        policy: PathPolicy,
        workspace_manager: WorkspaceManager,
        test_runner: TestRunner,
        budget: ExecutionBudget,
    ) -> None:
        self.workspace_dir = workspace_dir
        self.policy = policy
        self.workspace_manager = workspace_manager
        self.test_runner = test_runner
        self.budget = budget

        self.execution_history: list[tuple[ToolCall, ToolResult]] = []
        self._handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "inspect_repository": self._handle_inspect_repository,
            "search_code": self._handle_search_code,
            "read_file": self._handle_read_file,
            "edit_file": self._handle_edit_file,
            "run_tests": self._handle_run_tests,
        }

    def get_definitions(self) -> list[dict[str, Any]]:
        """Return registered tool schemas formatted for Ollama."""
        return get_tool_definitions()

    def execute(self, call: ToolCall) -> ToolResult:
        """Validate and dispatch a tool call."""
        # 1. Budget enforcement
        try:
            self.budget.record_tool_call()
        except BudgetExceededError as e:
            result = ToolResult(
                tool_name=call.name,
                success=False,
                output="",
                error=str(e),
            )
            self.execution_history.append((call, result))
            return result

        # 2. Handler lookup
        handler = self._handlers.get(call.name)
        if not handler:
            result = ToolResult(
                tool_name=call.name,
                success=False,
                output="",
                error=f"Tool '{call.name}' is not registered. Permitted tools: {list(self._handlers.keys())}",
            )
            self.execution_history.append((call, result))
            return result

        # 3. Execution
        try:
            raw_result = handler(call.arguments)
            success = bool(raw_result.get("success", False))
            error = raw_result.get("error")
            output_str = json.dumps(raw_result, indent=2)

            result = ToolResult(
                tool_name=call.name,
                success=success,
                output=output_str,
                error=error,
                data=raw_result,
            )
        except ToolArgumentError as e:
            result = ToolResult(
                tool_name=call.name,
                success=False,
                output="",
                error=f"Argument validation failed for '{call.name}': {e}",
            )
        except Exception as e:
            result = ToolResult(
                tool_name=call.name,
                success=False,
                output="",
                error=f"Execution error in '{call.name}': {e}",
            )

        self.execution_history.append((call, result))
        return result

    def _handle_inspect_repository(self, args: dict[str, Any]) -> dict[str, Any]:
        subpath = args.get("subpath")
        return inspect_repository(self.workspace_dir, self.policy, subpath)

    def _handle_search_code(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query")
        if not query or not isinstance(query, str):
            raise ToolArgumentError("Missing or invalid required argument 'query'.")
        path_filter = args.get("path_filter")
        max_results = args.get("max_results", 30)
        return search_code(self.workspace_dir, self.policy, query, path_filter, max_results)

    def _handle_read_file(self, args: dict[str, Any]) -> dict[str, Any]:
        path = args.get("path")
        if not path or not isinstance(path, str):
            raise ToolArgumentError("Missing or invalid required argument 'path'.")
        start_line = args.get("start_line")
        line_count = args.get("line_count")
        return read_file(self.workspace_dir, self.policy, path, start_line, line_count)

    def _handle_edit_file(self, args: dict[str, Any]) -> dict[str, Any]:
        path = args.get("path")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        if not path or not isinstance(path, str):
            raise ToolArgumentError("Missing or invalid required argument 'path'.")
        if old_text is None or not isinstance(old_text, str):
            raise ToolArgumentError("Missing or invalid required argument 'old_text'.")
        if new_text is None or not isinstance(new_text, str):
            raise ToolArgumentError("Missing or invalid required argument 'new_text'.")

        return edit_file(
            self.workspace_dir,
            self.policy,
            self.workspace_manager,
            path,
            old_text,
            new_text,
        )

    def _handle_run_tests(self, args: dict[str, Any]) -> dict[str, Any]:
        suite = args.get("suite")
        if not suite or not isinstance(suite, str):
            raise ToolArgumentError("Missing or invalid required argument 'suite'.")
        target = args.get("target")
        return run_tests_tool(self.workspace_dir, self.test_runner, suite, target)
