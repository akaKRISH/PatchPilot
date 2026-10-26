"""Command policy restricting test execution to vetted, predefined test suites."""

import re
import shutil
import sys

from patchpilot.errors import CommandPolicyError
from patchpilot.schemas import TestSuiteName

# Disallowed shell metacharacters
FORBIDDEN_SHELL_PATTERNS = re.compile(r"[;&|`$<>()>{}\n\r]")


class CommandPolicy:
    """Enforces execution policies on commands."""

    @classmethod
    def validate_test_target(cls, target: str | None) -> str | None:
        """Verify that a test target path does not contain shell injections."""
        if not target:
            return None
        target = target.strip()
        if FORBIDDEN_SHELL_PATTERNS.search(target):
            raise CommandPolicyError(f"Test target '{target}' contains forbidden shell characters.")
        # Prevent traversal in test target
        if ".." in target or target.startswith("/") or target.startswith("\\"):
            raise CommandPolicyError(
                f"Test target '{target}' must be a relative path within the repository."
            )
        return target

    @classmethod
    def build_test_command(
        cls,
        suite: TestSuiteName,
        python_executable: str | None = None,
        target: str | None = None,
    ) -> list[str]:
        """Construct safe argument list for a predefined test suite."""
        clean_target = cls.validate_test_target(target)
        python_exec = python_executable or sys.executable

        if suite == TestSuiteName.PYTEST:
            cmd = [python_exec, "-m", "pytest", "-v"]
            if clean_target:
                cmd.append(clean_target)
            return cmd

        elif suite == TestSuiteName.UNITTEST:
            cmd = [python_exec, "-m", "unittest"]
            if clean_target:
                cmd.extend(["discover", "-s", clean_target])
            else:
                cmd.extend(["discover", "-v"])
            return cmd

        elif suite == TestSuiteName.COMPILEALL:
            cmd = [python_exec, "-m", "compileall", "-q"]
            if clean_target:
                cmd.append(clean_target)
            else:
                cmd.append(".")
            return cmd

        elif suite == TestSuiteName.JEST:
            npx_bin = shutil.which("npx")
            if not npx_bin:
                raise CommandPolicyError("Node.js/npx toolchain is not available on PATH.")
            cmd = [npx_bin, "--no-install", "jest", "--verbose", "--colors=false"]
            if clean_target:
                cmd.append(clean_target)
            return cmd

        elif suite == TestSuiteName.GO_TEST:
            go_bin = shutil.which("go")
            if not go_bin:
                raise CommandPolicyError("Go toolchain is not available on PATH.")
            cmd = [go_bin, "test", "-v"]
            if clean_target:
                cmd.append(clean_target)
            else:
                cmd.append("./...")
            return cmd

        elif suite == TestSuiteName.CARGO_TEST:
            cargo_bin = shutil.which("cargo")
            if not cargo_bin:
                raise CommandPolicyError("Rust/cargo toolchain is not available on PATH.")
            cmd = [cargo_bin, "test"]
            if clean_target:
                cmd.extend([clean_target, "--", "--nocapture"])
            else:
                cmd.extend(["--", "--nocapture"])
            return cmd

        else:
            raise CommandPolicyError(f"Unsupported test suite: {suite}")

    @classmethod
    def build_docker_test_command(
        cls,
        suite: TestSuiteName,
        target: str | None = None,
    ) -> list[str]:
        """Construct safe in-container test command arguments."""
        clean_target = cls.validate_test_target(target)
        if suite == TestSuiteName.PYTEST:
            cmd = ["python", "-m", "pytest", "-v"]
            if clean_target:
                cmd.append(clean_target)
            return cmd
        elif suite == TestSuiteName.UNITTEST:
            cmd = ["python", "-m", "unittest", "discover", "-v"]
            if clean_target:
                cmd.extend(["-s", clean_target])
            return cmd
        elif suite == TestSuiteName.COMPILEALL:
            cmd = ["python", "-m", "compileall", "-q"]
            if clean_target:
                cmd.append(clean_target)
            else:
                cmd.append(".")
            return cmd
        elif suite in (TestSuiteName.JEST, TestSuiteName.GO_TEST, TestSuiteName.CARGO_TEST):
            raise CommandPolicyError(
                f"Test suite '{suite.value}' is not supported in the Python-only sandbox image. "
                "Multi-language test suites require host execution (--allow-host-execution) or a future dedicated multi-language image."
            )
        else:
            raise CommandPolicyError(f"Unsupported test suite for sandbox: {suite}")
