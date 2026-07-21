"""Numeric guards.

The PRD fragments listed ``NaN`` and ``Infinity`` twice as things that reach
the timing pipeline. Rather than sprinkle ``math.isfinite`` checks across the
codebase, every finiteness decision funnels through here (DRY). If we ever need
to change what "acceptable number" means (e.g. reject subnormals), it changes in
exactly one place.
"""
from __future__ import annotations

import math


def is_finite_number(value: object) -> bool:
    """True only for real, finite ints/floats.

    Explicitly rejects ``bool`` (a subclass of ``int``), ``NaN``, ``+/-inf``,
    strings, and ``None``. Client payloads are untrusted, so this is deliberately
    strict.
    """
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into ``[low, high]``. Assumes inputs are already finite."""
    return max(low, min(high, value))
