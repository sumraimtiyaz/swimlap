"""Lap timing validation.

Produces an ``is_valid`` verdict plus human-readable reasons. Invalid laps are
still *persisted* (with ``is_valid = False``) for audit — matching the PRD's
``is_valid`` column — but scoring ignores them. This keeps the ingest path
forgiving (never lose a keystroke) while keeping results clean.

Pure/stdlib; unit-tested directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import LapSource
from .numeric import is_finite_number
from .tuning import LapIngestTuning


@dataclass(frozen=True)
class LapCandidate:
    """The raw, untrusted timing payload for one tap."""

    seq: int
    device_mono_ms: float
    source: str


@dataclass(frozen=True)
class LapContext:
    """What the validator needs to know about the swim's prior state."""

    previous_seq: int | None        # highest seq already recorded for this swim
    previous_mono_ms: float | None  # monotonic reading of the previous accepted tap


@dataclass(frozen=True)
class LapVerdict:
    is_valid: bool
    reasons: tuple[str, ...]

    @property
    def is_duplicate(self) -> bool:
        return "duplicate_seq" in self.reasons


def validate_lap(candidate: LapCandidate, ctx: LapContext, tuning: LapIngestTuning) -> LapVerdict:
    """Return a verdict for one candidate lap. Never raises for *data* problems —
    it reports them, so a bad tap in a batch does not sink its neighbours."""
    reasons: list[str] = []

    # 1) Finiteness — the NaN/Infinity guard.
    if not is_finite_number(candidate.device_mono_ms):
        reasons.append("non_finite_mono")

    # 2) Sequence integrity.
    if not isinstance(candidate.seq, int) or isinstance(candidate.seq, bool) or candidate.seq < 0:
        reasons.append("bad_seq")
    elif ctx.previous_seq is not None:
        if candidate.seq == ctx.previous_seq:
            reasons.append("duplicate_seq")
        elif candidate.seq < ctx.previous_seq:
            reasons.append("out_of_order_seq")

    # 3) Source must be a known value.
    if candidate.source not in {s.value for s in LapSource}:
        reasons.append("unknown_source")

    # The remaining checks only make sense once we know the mono reading is finite.
    if is_finite_number(candidate.device_mono_ms) and ctx.previous_mono_ms is not None \
            and is_finite_number(ctx.previous_mono_ms):
        delta = candidate.device_mono_ms - ctx.previous_mono_ms
        # 4) A monotonic clock cannot go backwards on one device.
        if delta < 0:
            reasons.append("backwards_mono")
        # 5) Debounce: two taps closer than the minimum are almost certainly a
        #    double-tap / bounce, not two real laps.
        elif delta < tuning.min_inter_lap_ms:
            reasons.append("debounced")

    # Duplicates are handled idempotently upstream and are not, by themselves, an
    # "invalid" lap — they are simply ignored. Any *other* reason invalidates.
    hard_reasons = [r for r in reasons if r != "duplicate_seq"]
    return LapVerdict(is_valid=(len(hard_reasons) == 0), reasons=tuple(reasons))


def is_late(event_server_ts: datetime, swim_closed_at: datetime | None, tuning: LapIngestTuning) -> bool:
    """A lap is late if its arrival time falls after the swim closed (plus a small
    grace window)."""
    if swim_closed_at is None:
        return False
    return (event_server_ts - swim_closed_at).total_seconds() * 1000.0 > tuning.late_grace_ms
