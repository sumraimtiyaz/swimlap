"""Simulated reference generator (pure).

Produces the number each recorded lap is compared against. Per PRD §9 the rule is
deliberately minimal: **a base lap time plus small random variation. Nothing
more.** A configurable share of laps are marked ``is_valid = False`` to exercise
the path where a lap has no reference (what happens when real hardware misses a
touch).

Kept pure and injectable (the caller passes an ``random.Random``) so tests are
deterministic and the whole thing swaps for real hardware without touching
anything else.
"""
from __future__ import annotations

import random

from .tuning import ReferenceTuning


def generate_reference(tuning: ReferenceTuning, rng: random.Random) -> tuple[int, bool]:
    """Return ``(elapsed_ms, is_valid)`` for one simulated reference lap.

    ``failure_rate`` at 1.0 yields only invalid references; at 0.0, only valid
    ones (``random()`` is in ``[0, 1)``).
    """
    is_valid = rng.random() >= tuning.failure_rate
    variation = rng.uniform(-tuning.variation_ms, tuning.variation_ms)
    elapsed_ms = max(1, round(tuning.base_lap_ms + variation))
    return elapsed_ms, is_valid
