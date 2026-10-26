"""Unit tests for the calculator module."""

import pytest
from calculator import add, divide, multiply, subtract


def test_add() -> None:
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_subtract() -> None:
    assert subtract(5, 3) == 2
    assert subtract(10, 20) == -10


def test_multiply() -> None:
    assert multiply(4, 3) == 12
    assert multiply(-2, 3) == -6


def test_divide() -> None:
    assert divide(10, 2) == 5
    with pytest.raises(ValueError):
        divide(5, 0)
