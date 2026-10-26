"""Security tests verifying strict enforcement of tool execution permissions."""

import pytest

from patchpilot.config import PatchPilotConfig
from patchpilot.safety.limits import ExecutionBudget
from patchpilot.schemas import ToolCall
from patchpilot.tools.registry import ToolRegistry
from patchpilot.verification.runner import TestRunner
from patchpilot.workspace.manager import WorkspaceManager


@pytest.mark.security
def test_unregistered_tools_rejected(
    workspace_manager: WorkspaceManager,
    test_config: PatchPilotConfig,
) -> None:
    ws = workspace_manager.disposable_workspace
    policy = workspace_manager.disposable_policy
    assert policy is not None
    budget = ExecutionBudget()
    runner = TestRunner(test_config)
    registry = ToolRegistry(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=workspace_manager,
        test_runner=runner,
        budget=budget,
    )

    unauthorized_tools = [
        "bash",
        "sh",
        "powershell",
        "exec",
        "eval",
        "download_file",
        "git_commit",
        "install_package",
    ]

    for tool_name in unauthorized_tools:
        call = ToolCall(name=tool_name, arguments={"arg": "val"})
        res = registry.execute(call)
        assert res.success is False
        assert "not registered" in (res.error or "")
