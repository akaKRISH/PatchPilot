"""Self-healing repair loop orchestrating bounded model steps, tool execution, and verification."""

import contextlib
import logging

from patchpilot.agent.context_builder import ContextBuilder
from patchpilot.config import PatchPilotConfig
from patchpilot.errors import BudgetExceededError, OllamaError
from patchpilot.ollama_client import OllamaClient
from patchpilot.schemas import (
    FilePatchMetadata,
    RepairAttempt,
    TaskRequest,
    TestSuiteResult,
    VerificationSummary,
)
from patchpilot.tools.registry import ToolRegistry
from patchpilot.verification.regression import analyze_regressions

logger = logging.getLogger("patchpilot.repair_loop")


class RepairLoop:
    """Orchestrates bounded reasoning steps and verification retries."""

    def __init__(
        self,
        ollama_client: OllamaClient,
        tool_registry: ToolRegistry,
        task: TaskRequest,
        config: PatchPilotConfig,
        baseline_result: TestSuiteResult | None = None,
    ) -> None:
        self.client = ollama_client
        self.registry = tool_registry
        self.task = task
        self.config = config
        self.baseline_result = baseline_result
        self.context_builder = ContextBuilder(config.max_context_characters)
        self.fatal_error: str | None = None

    def run(self) -> tuple[list[RepairAttempt], VerificationSummary]:
        """Execute the self-healing repair loop up to configured max attempts."""
        attempts: list[RepairAttempt] = []
        final_verification = VerificationSummary(
            baseline_result=self.baseline_result,
            final_result=None,
            is_regression_free=False,
            verified=False,
        )

        messages = self.context_builder.build_initial_messages(self.task, self.baseline_result)
        tools = self.registry.get_definitions()
        max_provider_retries = 2
        consecutive_provider_failures = 0

        for attempt_idx in range(1, self.config.max_repair_attempts + 1):
            logger.info(f"Starting repair attempt {attempt_idx}/{self.config.max_repair_attempts}")
            attempt = RepairAttempt(attempt_number=attempt_idx)

            step_count = 0
            latest_test_result: TestSuiteResult | None = None
            fatal_provider_break = False

            while step_count < self.config.max_agent_steps:
                if self.registry.budget.is_exhausted():
                    attempt.notes = "Agent reasoning budget exhausted."
                    break

                messages = self.context_builder.prune_context(messages)

                try:
                    resp = self.client.chat(messages=messages, tools=tools)
                    consecutive_provider_failures = 0
                except OllamaError as e:
                    consecutive_provider_failures += 1
                    logger.error(
                        f"Model provider failure ({consecutive_provider_failures}/{max_provider_retries}): {e}"
                    )
                    attempt.notes = f"Provider failure: {e}"
                    if consecutive_provider_failures >= max_provider_retries:
                        self.fatal_error = f"Persistent provider failure: {e}"
                        attempt.notes = self.fatal_error
                        logger.error("Provider retry limit reached. Terminating repair loop.")
                        fatal_provider_break = True
                    break
                except Exception as e:
                    logger.error(f"Model chat failure: {e}")
                    attempt.notes = f"Model call failed: {e}"
                    break

                try:
                    self.registry.budget.step()
                    step_count += 1
                except BudgetExceededError as err:
                    logger.warning(f"Reasoning budget reached: {err}")
                    attempt.notes = str(err)
                    break

                msg = resp.get("message", {})
                content = msg.get("content", "")
                calls = self.client.parse_tool_calls(msg)

                # Record diagnosis or thought summary
                if content:
                    attempt.diagnosis += ("\n" if attempt.diagnosis else "") + content[:300]

                # If no tool calls produced by the model
                if not calls:
                    # Model produced text without calling tools
                    messages.append({"role": "assistant", "content": content})
                    # If model didn't call tools, prompt it to act
                    if step_count < self.config.max_agent_steps:
                        messages.append(
                            {
                                "role": "user",
                                "content": "Please invoke a registered tool (e.g. read_file, edit_file, run_tests) to proceed.",
                            }
                        )
                        continue
                    break

                # Execute tool calls
                messages.append(msg)  # assistant message with tool_calls
                for call in calls:
                    attempt.tool_calls.append(call)
                    result = self.registry.execute(call)
                    attempt.tool_results.append(result)

                    # Append tool result to messages
                    messages.append(
                        {
                            "role": "tool",
                            "content": result.output
                            if result.success
                            else f"Error: {result.error}",
                            "name": call.name,
                        }
                    )

                    # If edit_file was called and succeeded, record applied patch
                    if call.name == "edit_file" and result.success and result.data:
                        with contextlib.suppress(Exception):
                            patch_meta = FilePatchMetadata.model_validate(result.data)
                            attempt.applied_patches.append(patch_meta)

                    # If run_tests was called
                    if call.name == "run_tests" and result.success and result.data:
                        with contextlib.suppress(Exception):
                            latest_test_result = TestSuiteResult.model_validate(result.data)

                # If the model called run_tests and tests passed, or if files have been edited
                if latest_test_result and latest_test_result.passed:
                    break

            # If the model made edits but didn't run tests explicitly, trigger test run to verify
            if not latest_test_result and self.registry.workspace_manager.modified_relative_files:
                try:
                    latest_test_result = self.registry.test_runner.run_tests(
                        workspace_dir=self.registry.workspace_dir,
                        suite=self.task.test_suite,
                        target=self.task.test_target,
                    )
                except Exception as e:
                    attempt.notes = f"Post-attempt test run failed: {e}"

            attempt.test_result = latest_test_result

            # Analyze regressions
            verification = analyze_regressions(self.baseline_result, latest_test_result)
            final_verification = verification

            if verification.verified:
                attempt.success = True
                attempts.append(attempt)
                logger.info(f"Attempt {attempt_idx} successfully verified! Stopping repair loop.")
                return attempts, final_verification
            else:
                attempt.success = False
                attempts.append(attempt)

                if fatal_provider_break or self.fatal_error:
                    logger.error("Stopping repair loop due to fatal provider error.")
                    return attempts, final_verification

                # If more attempts remain, format failure summary for retry
                if attempt_idx < self.config.max_repair_attempts:
                    fail_summary = (
                        latest_test_result.summary
                        if latest_test_result
                        else "No tests were executed or test run failed."
                    )
                    retry_msg = self.context_builder.build_retry_message(attempt_idx, fail_summary)
                    messages.append(retry_msg)

        return attempts, final_verification
