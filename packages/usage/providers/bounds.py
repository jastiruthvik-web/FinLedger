"""Shared checks for timeouts and byte caps. Booleans are rejected; they are an int subclass."""

from __future__ import annotations

import math


def require_positive_finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("timeout must be a positive finite number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("timeout must be a positive finite number")
    return number


def require_positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("payload bounds must be positive integers")
    return value
