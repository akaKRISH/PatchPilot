"""Execution limits and budget tracking for agent steps and tool calls."""

from patchpilot.errors import BudgetExceededError


class ExecutionBudget:
    """Tracks and enforces limits on agent steps and tool executions."""

    def __init__(self, max_steps: int = 12, max_tool_calls: int = 24) -> None:
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.current_steps = 0
        self.current_tool_calls = 0

    def step(self) -> None:
        """Increment and validate agent reasoning step count."""
        self.current_steps += 1
        if self.current_steps > self.max_steps:
            raise BudgetExceededError(
                f"Agent exceeded maximum reasoning steps budget ({self.max_steps})."
            )

    def record_tool_call(self) -> None:
        """Increment and validate tool call count."""
        self.current_tool_calls += 1
        if self.current_tool_calls > self.max_tool_calls:
            raise BudgetExceededError(
                f"Agent exceeded maximum tool calls budget ({self.max_tool_calls})."
            )

    def is_exhausted(self) -> bool:
        """Check if any budget limit has been reached."""
        return (
            self.current_steps >= self.max_steps or self.current_tool_calls >= self.max_tool_calls
        )
