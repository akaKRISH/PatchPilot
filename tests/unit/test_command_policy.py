"""Unit tests for command policies and execution argument builders."""

import pytest

from patchpilot.errors import CommandPolicyError
from patchpilot.safety.commands import CommandPolicy
from patchpilot.schemas import TestSuiteName


def test_build_pytest_command() -> None:
    cmd = CommandPolicy.build_test_command(TestSuiteName.PYTEST, "python.exe", "tests/test_foo.py")
    assert cmd == ["python.exe", "-m", "pytest", "-v", "tests/test_foo.py"]

    docker_cmd = CommandPolicy.build_docker_test_command(TestSuiteName.PYTEST, "tests/test_foo.py")
    assert docker_cmd == ["python", "-m", "pytest", "-v", "tests/test_foo.py"]


def test_build_unittest_command() -> None:
    cmd = CommandPolicy.build_test_command(TestSuiteName.UNITTEST, "python.exe", None)
    assert cmd == ["python.exe", "-m", "unittest", "discover", "-v"]

    docker_cmd = CommandPolicy.build_docker_test_command(TestSuiteName.UNITTEST, None)
    assert docker_cmd == ["python", "-m", "unittest", "discover", "-v"]


def test_build_compileall_command() -> None:
    cmd = CommandPolicy.build_test_command(TestSuiteName.COMPILEALL, "python.exe", None)
    assert cmd == ["python.exe", "-m", "compileall", "-q", "."]

    docker_cmd = CommandPolicy.build_docker_test_command(TestSuiteName.COMPILEALL, None)
    assert docker_cmd == ["python", "-m", "compileall", "-q", "."]


def test_build_jest_command() -> None:
    with pytest.raises(CommandPolicyError) as exc_info:
        CommandPolicy.build_docker_test_command(TestSuiteName.JEST, "tests/math.test.js")
    assert "not supported in the Python-only sandbox" in str(exc_info.value)

    cmd_host = CommandPolicy.build_test_command(TestSuiteName.JEST, target="tests/math.test.js")
    assert "jest" in cmd_host
    assert cmd_host[-1] == "tests/math.test.js"


def test_build_go_test_command() -> None:
    with pytest.raises(CommandPolicyError) as exc_info:
        CommandPolicy.build_docker_test_command(TestSuiteName.GO_TEST, "pkg/calc")
    assert "not supported in the Python-only sandbox" in str(exc_info.value)

    cmd_host = CommandPolicy.build_test_command(TestSuiteName.GO_TEST, target="pkg/calc")
    assert "go" in cmd_host[0].lower()
    assert cmd_host[-1] == "pkg/calc"


def test_build_cargo_test_command() -> None:
    with pytest.raises(CommandPolicyError) as exc_info:
        CommandPolicy.build_docker_test_command(TestSuiteName.CARGO_TEST, "test_add")
    assert "not supported in the Python-only sandbox" in str(exc_info.value)

    cmd_host = CommandPolicy.build_test_command(TestSuiteName.CARGO_TEST, target="test_add")
    assert "cargo" in cmd_host[0].lower()
    assert "test_add" in cmd_host


def test_forbidden_shell_characters_rejected() -> None:
    with pytest.raises(CommandPolicyError):
        CommandPolicy.validate_test_target("tests/test_foo.py; rm -rf /")

    with pytest.raises(CommandPolicyError):
        CommandPolicy.validate_test_target("tests/test_foo.py && echo pwned")

    with pytest.raises(CommandPolicyError):
        CommandPolicy.validate_test_target("tests/`whoami`")
