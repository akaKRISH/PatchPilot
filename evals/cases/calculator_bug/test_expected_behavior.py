"""Test expected behavior fixture for eval."""

from calculator import add, divide, multiply, subtract


def test_add_fixed() -> None:
    assert add(2, 3) == 5
    assert add(-1, 1) == 0


def test_existing_unbroken() -> None:
    assert subtract(10, 5) == 5
    assert multiply(3, 4) == 12
    assert divide(8, 2) == 4
