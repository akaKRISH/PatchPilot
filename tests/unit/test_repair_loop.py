"""Unit tests for the self-healing repair loop."""

from unittest.mock import MagicMock

from patchpilot.agent.repair_loop import RepairLoop
from patchpilot.config import PatchPilotConfig
from patchpilot.ollama_client import OllamaClient
from patchpilot.safety.limits import ExecutionBudget
from patchpilot.schemas import TaskRequest, TestSuiteName, TestSuiteResult
from patchpilot.tools.registry import ToolRegistry
from patchpilot.verification.runner import TestRunner
from patchpilot.workspace.manager import WorkspaceManager


def test_repair_loop_terminates_on_success(
    workspace_manager: WorkspaceManager,
    test_config: PatchPilotConfig,
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

    # Mock Ollama client that edits the file then runs tests
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.chat.side_effect = [
        {
            "message": {
                "role": "assistant",
                "content": "Fixing calculator bug",
                "tool_calls": [
                    {
                        "function": {
                            "name": "edit_file",
                            "arguments": {
                                "path": "calculator.py",
                                "old_text": "def add(a, b):\n    return a - b",
                                "new_text": "def add(a, b):\n    return a + b",
                            },
                        }
                    }
                ],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "Running tests to verify",
                "tool_calls": [
                    {
                        "function": {
                            "name": "run_tests",
                            "arguments": {"suite": "pytest", "target": "tests/test_calculator.py"},
                        }
                    }
                ],
            }
        },
    ]

    from patchpilot.schemas import ToolCall

    mock_client.parse_tool_calls.side_effect = [
        [
            ToolCall(
                name="edit_file",
                arguments={
                    "path": "calculator.py",
                    "old_text": "def add(a, b):\n    return a - b",
                    "new_text": "def add(a, b):\n    return a + b",
                },
            )
        ],
        [
            ToolCall(
                name="run_tests",
                arguments={"suite": "pytest", "target": "tests/test_calculator.py"},
            )
        ],
    ]

    task = TaskRequest(
        repo_path=str(workspace_manager.source_repo),
        task_description="Fix add function",
        test_suite=TestSuiteName.PYTEST,
        test_target="tests/test_calculator.py",
    )

    from patchpilot.schemas import TestCaseResult

    baseline = TestSuiteResult(
        suite_name=TestSuiteName.PYTEST,
        exit_code=1,
        passed=False,
        summary="1 failed, 1 passed",
        test_cases=[
            TestCaseResult(test_id="test_add", passed=False),
            TestCaseResult(test_id="test_subtract", passed=True),
        ],
    )

    loop = RepairLoop(
        ollama_client=mock_client,
        tool_registry=registry,
        task=task,
        config=test_config,
        baseline_result=baseline,
    )

    attempts, verification = loop.run()
    assert len(attempts) >= 1
    assert verification.verified is True
    assert len(attempts[0].applied_patches) == 1
    assert attempts[0].applied_patches[0].relative_path == "calculator.py"
    assert attempts[0].applied_patches[0].lines_added > 0
    assert attempts[0].applied_patches[0].lines_removed > 0


def test_repair_loop_bounded_provider_retries(
    workspace_manager: WorkspaceManager,
    test_config: PatchPilotConfig,
) -> None:
    from patchpilot.errors import OllamaResponseError

    ws = workspace_manager.disposable_workspace
    policy = workspace_manager.disposable_policy
    assert policy is not None
    budget = ExecutionBudget(max_steps=12, max_tool_calls=12)
    runner = TestRunner(test_config)

    registry = ToolRegistry(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=workspace_manager,
        test_runner=runner,
        budget=budget,
    )

    # Mock client that raises HTTP 500 on chat
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.chat.side_effect = OllamaResponseError(
        "Ollama chat request failed with HTTP 500: internal error",
        status_code=500,
        response_body="internal error",
    )

    task = TaskRequest(
        repo_path=str(workspace_manager.source_repo),
        task_description="Fix add function",
        test_suite=TestSuiteName.PYTEST,
    )

    test_config_with_retries = test_config.model_copy(update={"max_repair_attempts": 5})
    loop = RepairLoop(
        ollama_client=mock_client,
        tool_registry=registry,
        task=task,
        config=test_config_with_retries,
        baseline_result=None,
    )

    attempts, verification = loop.run()

    # Provider errors should NOT advance reasoning steps
    assert budget.current_steps == 0
    # Must terminate promptly after 2 provider retries (not spin all 5 configured attempts)
    assert len(attempts) == 2
    assert loop.fatal_error is not None
    assert "Persistent provider failure" in loop.fatal_error
    assert "HTTP 500" in loop.fatal_error
    assert verification.verified is False


def test_repair_loop_text_only_until_budget_exhaustion(
    workspace_manager: WorkspaceManager,
    test_config: PatchPilotConfig,
) -> None:
    ws = workspace_manager.disposable_workspace
    policy = workspace_manager.disposable_policy
    assert policy is not None
    budget = ExecutionBudget(max_steps=3, max_tool_calls=3)
    runner = TestRunner(test_config)

    registry = ToolRegistry(
        workspace_dir=ws,
        policy=policy,
        workspace_manager=workspace_manager,
        test_runner=runner,
        budget=budget,
    )

    # Mock client that only produces conversational text with NO tool calls
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.chat.return_value = {
        "message": {
            "role": "assistant",
            "content": "I am thinking about the problem...",
        }
    }
    mock_client.parse_tool_calls.return_value = []

    task = TaskRequest(
        repo_path=str(workspace_manager.source_repo),
        task_description="Fix add function",
        test_suite=TestSuiteName.PYTEST,
    )

    loop = RepairLoop(
        ollama_client=mock_client,
        tool_registry=registry,
        task=task,
        config=test_config.model_copy(update={"max_agent_steps": 3, "max_repair_attempts": 1}),
        baseline_result=None,
    )

    attempts, verification = loop.run()
    assert len(attempts) == 1
    assert budget.current_steps >= 3
    assert verification.verified is False


def test_repair_loop_records_only_successful_edits(
    workspace_manager: WorkspaceManager,
    test_config: PatchPilotConfig,
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

    from patchpilot.schemas import TestCaseResult, ToolCall

    # Client returns 1 failed edit, 1 successful edit, 1 run_tests
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.chat.side_effect = [
        {
            "message": {
                "role": "assistant",
                "content": "Trying bad edit",
                "tool_calls": [
                    {
                        "function": {
                            "name": "edit_file",
                            "arguments": {
                                "path": "calculator.py",
                                "old_text": "non_existent_text_to_replace",
                                "new_text": "replacement",
                            },
                        }
                    }
                ],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "Applying good edit",
                "tool_calls": [
                    {
                        "function": {
                            "name": "edit_file",
                            "arguments": {
                                "path": "calculator.py",
                                "old_text": "def add(a, b):\n    return a - b",
                                "new_text": "def add(a, b):\n    return a + b",
                            },
                        }
                    }
                ],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "Running test suite",
                "tool_calls": [
                    {
                        "function": {
                            "name": "run_tests",
                            "arguments": {"suite": "pytest", "target": "tests/test_calculator.py"},
                        }
                    }
                ],
            }
        },
    ]

    mock_client.parse_tool_calls.side_effect = [
        [
            ToolCall(
                name="edit_file",
                arguments={
                    "path": "calculator.py",
                    "old_text": "non_existent_text_to_replace",
                    "new_text": "replacement",
                },
            )
        ],
        [
            ToolCall(
                name="edit_file",
                arguments={
                    "path": "calculator.py",
                    "old_text": "def add(a, b):\n    return a - b",
                    "new_text": "def add(a, b):\n    return a + b",
                },
            )
        ],
        [
            ToolCall(
                name="run_tests",
                arguments={"suite": "pytest", "target": "tests/test_calculator.py"},
            )
        ],
    ]

    task = TaskRequest(
        repo_path=str(workspace_manager.source_repo),
        task_description="Fix add function",
        test_suite=TestSuiteName.PYTEST,
        test_target="tests/test_calculator.py",
    )

    baseline = TestSuiteResult(
        suite_name=TestSuiteName.PYTEST,
        exit_code=1,
        passed=False,
        summary="1 failed, 1 passed",
        test_cases=[
            TestCaseResult(test_id="test_add", passed=False),
            TestCaseResult(test_id="test_subtract", passed=True),
        ],
    )

    loop = RepairLoop(
        ollama_client=mock_client,
        tool_registry=registry,
        task=task,
        config=test_config,
        baseline_result=baseline,
    )

    attempts, verification = loop.run()
    assert len(attempts) == 1
    # Exactly one patch recorded: the successful one! The failed one is excluded.
    assert len(attempts[0].applied_patches) == 1
    assert attempts[0].applied_patches[0].relative_path == "calculator.py"
    assert verification.verified is True


def test_repair_loop_failed_edits_not_recorded(
    workspace_manager: WorkspaceManager,
    test_config: PatchPilotConfig,
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

    from patchpilot.schemas import TestCaseResult, ToolCall

    # Client returns only a failing edit, then runs tests (which still fail)
    mock_client = MagicMock(spec=OllamaClient)
    mock_client.chat.side_effect = [
        {
            "message": {
                "role": "assistant",
                "content": "Trying bad edit",
                "tool_calls": [
                    {
                        "function": {
                            "name": "edit_file",
                            "arguments": {
                                "path": "calculator.py",
                                "old_text": "non_existent_text_to_replace",
                                "new_text": "replacement",
                            },
                        }
                    }
                ],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "Running test suite",
                "tool_calls": [
                    {
                        "function": {
                            "name": "run_tests",
                            "arguments": {"suite": "pytest", "target": "tests/test_calculator.py"},
                        }
                    }
                ],
            }
        },
    ]

    mock_client.parse_tool_calls.side_effect = [
        [
            ToolCall(
                name="edit_file",
                arguments={
                    "path": "calculator.py",
                    "old_text": "non_existent_text_to_replace",
                    "new_text": "replacement",
                },
            )
        ],
        [
            ToolCall(
                name="run_tests",
                arguments={"suite": "pytest", "target": "tests/test_calculator.py"},
            )
        ],
    ]

    task = TaskRequest(
        repo_path=str(workspace_manager.source_repo),
        task_description="Fix add function",
        test_suite=TestSuiteName.PYTEST,
        test_target="tests/test_calculator.py",
    )

    baseline = TestSuiteResult(
        suite_name=TestSuiteName.PYTEST,
        exit_code=1,
        passed=False,
        summary="1 failed, 1 passed",
        test_cases=[
            TestCaseResult(test_id="test_add", passed=False),
            TestCaseResult(test_id="test_subtract", passed=True),
        ],
    )

    loop = RepairLoop(
        ollama_client=mock_client,
        tool_registry=registry,
        task=task,
        config=test_config.model_copy(update={"max_repair_attempts": 1}),
        baseline_result=baseline,
    )

    attempts, verification = loop.run()
    assert len(attempts) == 1
    # No patches were successfully applied!
    assert len(attempts[0].applied_patches) == 0
    assert verification.verified is False
