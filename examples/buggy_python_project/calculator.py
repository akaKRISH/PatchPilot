"""A basic arithmetic calculator module with a defect in the add function."""


def add(a: float, b: float) -> float:
    """Return the sum of a and b.

    BUG: Incorrectly subtracts b from a.
    """
    return a - b


def subtract(a: float, b: float) -> float:
    """Return the difference between a and b."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of a and b."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return the quotient of a divided by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
