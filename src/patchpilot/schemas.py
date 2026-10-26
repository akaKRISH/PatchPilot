"""Pydantic schemas and data contracts for PatchPilot."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class RepairStatus(StrEnum):
    """Enumeration of final repair outcome statuses."""

    FIXED = "FIXED"
    PARTIALLY_FIXED = "PARTIALLY_FIXED"
    UNRESOLVED = "UNRESOLVED"
    FAILED_SAFETY_CHECK = "FAILED_SAFETY_CHECK"
    CANCELLED = "CANCELLED"


class TestSuiteName(StrEnum):
    """Permitted predefined test suites."""

    __test__ = False

    PYTEST = "pytest"
    UNITTEST = "unittest"
    COMPILEALL = "compileall"
    JEST = "jest"
    GO_TEST = "go_test"
    CARGO_TEST = "cargo_test"


class TaskRequest(BaseModel):
    """User input task describing a bug and target repository."""

    repo_path: str = Field(..., description="Path to the user target repository")
    task_description: str = Field(..., description="Description of the bug to resolve")
    test_suite: TestSuiteName = Field(
        default=TestSuiteName.PYTEST, description="Predefined test suite to execute"
    )
    test_target: str | None = Field(
        default=None, description="Optional targeted test file or directory"
    )


class ManifestEntry(BaseModel):
    """Record of an individual file in a repository."""

    relative_path: str
    sha256: str
    size_bytes: int


class RepositoryManifest(BaseModel):
    """Snapshot of files and cryptographic hashes in a repository."""

    root_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entries: dict[str, ManifestEntry] = Field(default_factory=dict)

    def compute_diff(self, other: "RepositoryManifest") -> tuple[list[str], list[str], list[str]]:
        """Return (added, modified, deleted) relative paths compared to other."""
        current_keys = set(self.entries.keys())
        other_keys = set(other.entries.keys())

        added = sorted(other_keys - current_keys)
        deleted = sorted(current_keys - other_keys)
        modified = sorted(
            [
                k
                for k in current_keys & other_keys
                if self.entries[k].sha256 != other.entries[k].sha256
            ]
        )
        return added, modified, deleted


class ToolCall(BaseModel):
    """A tool invocation requested by the agent."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str | None = None


class ToolResult(BaseModel):
    """The result of executing a tool."""

    tool_name: str
    success: bool
    output: str
    error: str | None = None
    data: dict[str, Any] | None = None


class TestCaseResult(BaseModel):
    """Outcome of a single test case within a suite."""

    __test__ = False

    test_id: str
    passed: bool
    duration_seconds: float = 0.0
    failure_message: str | None = None


class TestSuiteResult(BaseModel):
    """Outcome of executing a test suite."""

    __test__ = False
    model_config = ConfigDict(populate_by_name=True)

    suite_name: TestSuiteName = Field(validation_alias=AliasChoices("suite_name", "suite"))
    exit_code: int
    passed: bool
    summary: str
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    test_cases: list[TestCaseResult] = Field(default_factory=list)
    raw_output: str = ""
    duration_seconds: float = 0.0


class FilePatchMetadata(BaseModel):
    """Metadata about edits applied to an individual file."""

    model_config = ConfigDict(populate_by_name=True)

    relative_path: str = Field(validation_alias=AliasChoices("relative_path", "path"))
    before_sha256: str
    after_sha256: str
    lines_added: int = 0
    lines_removed: int = 0


class PatchArtifact(BaseModel):
    """Collection of file changes and the generated unified diff."""

    changed_files: list[FilePatchMetadata] = Field(default_factory=list)
    unified_diff: str = ""


class RepairAttempt(BaseModel):
    """Record of an individual repair attempt during the repair loop."""

    attempt_number: int
    diagnosis: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    applied_patches: list[FilePatchMetadata] = Field(default_factory=list)
    test_result: TestSuiteResult | None = None
    success: bool = False
    notes: str | None = None


class VerificationSummary(BaseModel):
    """Comparison of baseline test execution vs. post-repair test execution."""

    baseline_result: TestSuiteResult | None = None
    final_result: TestSuiteResult | None = None
    fixed_tests: list[str] = Field(default_factory=list)
    persisting_failures: list[str] = Field(default_factory=list)
    regression_tests: list[str] = Field(default_factory=list)
    is_regression_free: bool = True
    verified: bool = False


class RunReport(BaseModel):
    """Structured report produced at the conclusion of a repair run."""

    run_id: str
    task: TaskRequest
    status: RepairStatus
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    attempts_made: int
    max_attempts: int
    attempts: list[RepairAttempt] = Field(default_factory=list)
    verification: VerificationSummary | None = None
    patch: PatchArtifact | None = None
    original_repo_unmodified: bool = True
    safety_violations: list[str] = Field(default_factory=list)
    error_message: str | None = None


class BenchmarkCase(BaseModel):
    """Definition of an evaluation case in the benchmark."""

    case_id: str
    name: str
    description: str
    source_dir: str
    task_description: str
    test_suite: TestSuiteName
    targeted_test: str | None = None
    expected_status: RepairStatus = RepairStatus.FIXED


class EvalResult(BaseModel):
    """Evaluation result for an individual benchmark case."""

    case_id: str
    success: bool
    status: RepairStatus
    duration_seconds: float
    attempts: int
    tool_calls_count: int
    regression_detected: bool
    error: str | None = None


class EvalReport(BaseModel):
    """Overall benchmark evaluation report."""

    total_cases: int
    passed_cases: int
    failed_cases: int
    success_rate: float
    total_duration_seconds: float
    results: list[EvalResult] = Field(default_factory=list)
