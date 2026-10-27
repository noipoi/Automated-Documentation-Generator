"""Simple calculator utilities.

This module is the sample input for the documentation generator. It contains
plain functions, an async function and a class with several kinds of methods.
"""

from __future__ import annotations


def add(a: int, b: int) -> int:
    """Return the sum of ``a`` and ``b``."""
    return a + b


def divide(numerator: float, denominator: float = 1.0) -> float:
    """Divide ``numerator`` by ``denominator``.

    Raises:
        ZeroDivisionError: if ``denominator`` is zero.
    """
    return numerator / denominator


def mean(*values: float, default: float | None = None) -> float | None:
    """Return the arithmetic mean, or ``default`` when no values are given."""
    if not values:
        return default
    return sum(values) / len(values)


async def delayed_add(a: int, b: int) -> int:
    """Asynchronously add two integers."""
    return a + b


def _internal_helper(x):
    return x


class Calculator:
    """A calculator that remembers its last result."""

    def __init__(self, start: float = 0.0) -> None:
        """Create a calculator whose memory starts at ``start``."""
        self.memory = start

    def add(self, value: float) -> float:
        """Add ``value`` to the memory and return the new memory."""
        self.memory += value
        return self.memory

    @staticmethod
    def square(x: float) -> float:
        """Return ``x`` squared."""
        return x * x

    @classmethod
    def from_values(cls, values: list[float]) -> "Calculator":
        """Build a calculator whose memory is the sum of ``values``."""
        return cls(sum(values))

    async def reset(self) -> None:
        """Clear the memory."""
        self.memory = 0.0

    def no_docs(self, flag: bool | None = None):
        return flag
