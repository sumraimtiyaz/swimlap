"""Canonical domain enumerations.

Values here are wire values and MUST match ``shared/contracts/contract.json``.
``tests/test_contract_sync.py`` enforces that invariant so the three apps never
drift apart.
"""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    COORDINATOR = "coordinator"
    TIMER = "timer"


class SwimStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    CLOSED = "closed"


class ClosureMethod(str, Enum):
    TIMER_COMPLETED = "timer_completed"
    AUTO_INACTIVITY = "auto_inactivity"
    COORDINATOR = "coordinator"


class LapSource(str, Enum):
    MANUAL = "manual"
    SIMULATED = "simulated"
