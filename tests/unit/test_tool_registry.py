"""Unit tests for tool registry execution and validation."""

from patchpilot.config import PatchPilotConfig
from patchpilot.safety.limits import ExecutionBudget
from patchpilot.schemas import ToolCall
from patchpilot.tools.registry import ToolRegistry
from patchpilot.verification.runner import TestRunner
from patchpilot.workspace.manager import WorkspaceManager


def test_tool_registry_valid_read(
    workspace_manager: WorkspaceManager, test_config: PatchPilotConfig
) -> None:
    ws = workspace_manager.disposable_workspace
    policy = workspace_manager.disposable_policy
    assert policy is not None
    budget = ExecutionBudget(max_steps=5, max_tool_calls=5)
    runner = TestRunner(test_config)

    registry = ToolRegistry(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=workspace_manager,
        test_runner=runner,
        budget=budget,
    )

    call = ToolCall(name="read_file", arguments={"path": "calculator.py"})
    result = registry.execute(call)
    assert result.success is True
    assert "calculator" in result.output
    assert budget.current_tool_calls == 1


def test_tool_registry_unknown_tool(
    workspace_manager: WorkspaceManager, test_config: PatchPilotConfig
) -> None:
    ws = workspace_manager.disposable_workspace
    policy = workspace_manager.disposable_policy
    assert policy is not None
    budget = ExecutionBudget(max_steps=5, max_tool_calls=5)
    runner = TestRunner(test_config)

    registry = ToolRegistry(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=workspace_manager,
        test_runner=runner,
        budget=budget,
    )

    call = ToolCall(name="dangerous_shell", arguments={"cmd": "whoami"})
    result = registry.execute(call)
    assert result.success is False
    assert "not registered" in (result.error or "")


def test_tool_registry_budget_exhaustion(
    workspace_manager: WorkspaceManager, test_config: PatchPilotConfig
) -> None:
    ws = workspace_manager.disposable_workspace
    policy = workspace_manager.disposable_policy
    assert policy is not None
    budget = ExecutionBudget(max_steps=5, max_tool_calls=1)
    runner = TestRunner(test_config)

    registry = ToolRegistry(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=workspace_manager,
        test_runner=runner,
        budget=budget,
    )

    call = ToolCall(name="inspect_repository", arguments={})
    res1 = registry.execute(call)
    assert res1.success is True

    # Second call should fail due to budget
    res2 = registry.execute(call)
    assert res2.success is False
    assert "budget" in (res2.error or "").lower()
