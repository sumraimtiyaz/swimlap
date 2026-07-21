"""Swim lifecycle state machine.

    scheduled --first capture--> live --close(method)--> closed

Transitions are guarded in one place so no service can put a swim into an
impossible state. Closure carries a ``ClosureMethod`` (``timer_completed`` when
the timer marks the practice done, ``auto_inactivity`` when no laps arrive for a
while, or ``coordinator`` when a coordinator ends it). A closed swim is final —
there is no reopen.

Pure/stdlib; unit-tested directly.
"""
from __future__ import annotations

from datetime import datetime

from .enums import ClosureMethod, SwimStatus
from .errors import DomainError, ErrorCode

# Allowed forward transitions. Anything not listed is illegal.
_ALLOWED: dict[SwimStatus, frozenset[SwimStatus]] = {
    SwimStatus.SCHEDULED: frozenset({SwimStatus.LIVE}),
    SwimStatus.LIVE: frozenset({SwimStatus.CLOSED}),
    SwimStatus.CLOSED: frozenset(),
}


def can_transition(current: SwimStatus, target: SwimStatus) -> bool:
    return target in _ALLOWED.get(current, frozenset())


def assert_transition(current: SwimStatus, target: SwimStatus) -> None:
    if not can_transition(current, target):
        raise DomainError(
            ErrorCode.ILLEGAL_STATE_TRANSITION,
            f"Cannot move swim from {current.value} to {target.value}.",
            {"from": current.value, "to": target.value},
        )


def can_accept_lap_submission(status: SwimStatus) -> bool:
    """Whether the server will *accept* a lap batch at all.

    A swim that has just closed must still accept **buffered** laps that a phone
    captured while it was live but only managed to upload afterwards — otherwise
    offline captures are lost. Such laps are flagged ``was_late`` and excluded
    from the average. Only a swim that never started (``scheduled``) accepts a
    submission too — the first capture is what takes it live.
    """
    return status in (SwimStatus.SCHEDULED, SwimStatus.LIVE, SwimStatus.CLOSED)


def should_auto_close_for_inactivity(
    *,
    last_activity: datetime | None,
    now: datetime,
    timeout_seconds: int,
) -> bool:
    """Decide whether a live swim has gone quiet long enough to auto-close.

    ``last_activity`` is the server timestamp of the most recent lap. A live swim
    always has at least one lap (the first capture is what took it live), so this
    is never ``None`` in practice; the guard is defensive.
    """
    if last_activity is None:
        return False
    return (now - last_activity).total_seconds() >= timeout_seconds


def closure_method_for(*, timer_completed: bool, triggered_by_inactivity: bool) -> ClosureMethod:
    """Pick the closure reason. Explicit completion wins over inactivity."""
    if timer_completed:
        return ClosureMethod.TIMER_COMPLETED
    if triggered_by_inactivity:
        return ClosureMethod.AUTO_INACTIVITY
    return ClosureMethod.COORDINATOR
