"""Context builder formatting bounded message histories for the model."""

from typing import Any

from patchpilot.agent.prompts import RETRY_PROMPT_TEMPLATE, SYSTEM_PROMPT, TASK_PROMPT_TEMPLATE
from patchpilot.safety.redaction import redact_sensitive_text
from patchpilot.schemas import TaskRequest, TestSuiteResult


class ContextBuilder:
    """Constructs and manages bounded prompt context for Ollama chat."""

    def __init__(self, max_context_chars: int = 50000) -> None:
        self.max_context_chars = max_context_chars

    def build_initial_messages(
        self,
        task: TaskRequest,
        baseline_result: TestSuiteResult | None = None,
    ) -> list[dict[str, Any]]:
        """Construct the initial system and task prompt messages."""
        target_info = (
            f"TARGET TEST FILE: {task.test_target}"
            if task.test_target
            else "TARGET TEST: Entire suite"
        )
        baseline_summary = (
            baseline_result.summary if baseline_result else "Baseline not run or clean."
        )

        user_content = TASK_PROMPT_TEMPLATE.format(
            task_description=task.task_description,
            test_suite=task.test_suite.value,
            test_target_info=target_info,
            baseline_summary=baseline_summary,
        )

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    def build_retry_message(
        self,
        attempt_number: int,
        failure_summary: str,
    ) -> dict[str, Any]:
        """Construct a failure diagnostic message for retrying."""
        content = RETRY_PROMPT_TEMPLATE.format(
            attempt_number=attempt_number,
            failure_summary=redact_sensitive_text(failure_summary),
        )
        return {"role": "user", "content": content}

    def prune_context(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure total message character length does not exceed max_context_chars."""
        total_len = sum(len(str(m.get("content", ""))) for m in messages)
        if total_len <= self.max_context_chars:
            return messages

        # Preserve system prompt and latest user/assistant messages; trim middle tool outputs
        pruned = list(messages)
        for i in range(2, len(pruned) - 2):
            content = str(pruned[i].get("content", ""))
            if len(content) > 500:
                pruned[i]["content"] = content[:500] + "... [TRUNCATED CONTEXT]"

        return pruned
