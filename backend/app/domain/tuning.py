"""Timing tuning constants.

Loaded from ``shared/contracts/contract.json`` at import time so the backend and
both clients read the *same* numbers. If the file cannot be found (e.g. the
backend is deployed as a standalone wheel), we fall back to a committed default
so the service still boots. ``tests/test_contract_sync.py`` verifies the
fallback matches the JSON.

Pure stdlib on purpose: the domain layer must be importable and testable without
FastAPI, pydantic, or a database.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LapIngestTuning:
    late_grace_ms: float = 1500
    max_laps_per_batch: int = 500
    min_inter_lap_ms: float = 250


@dataclass(frozen=True)
class SwimTuning:
    auto_inactivity_timeout_seconds: int = 900
    default_lane_count: int = 8
    max_lane_count: int = 12


@dataclass(frozen=True)
class AuthTuning:
    token_ttl_hours: int = 24
    max_failed_attempts: int = 5
    lockout_minutes: int = 15


@dataclass(frozen=True)
class ReferenceTuning:
    base_lap_ms: float = 40_000
    variation_ms: float = 1_500
    failure_rate: float = 0.0


@dataclass(frozen=True)
class Tuning:
    lap_ingest: LapIngestTuning
    swim: SwimTuning
    auth: AuthTuning
    reference: ReferenceTuning


def _contract_path() -> Path:
    # backend/app/domain/tuning.py -> repo root is three parents up from app/
    return Path(__file__).resolve().parents[3] / "shared" / "contracts" / "contract.json"


def _load() -> Tuning:
    defaults = Tuning(LapIngestTuning(), SwimTuning(), AuthTuning(), ReferenceTuning())
    try:
        raw = json.loads(_contract_path().read_text(encoding="utf-8"))["timing"]
    except (FileNotFoundError, KeyError, ValueError):
        return defaults

    li, sw, au, ref = raw.get("lapIngest", {}), raw.get("swim", {}), raw.get("auth", {}), raw.get("reference", {})
    return Tuning(
        lap_ingest=LapIngestTuning(
            late_grace_ms=li.get("lateGraceMs", defaults.lap_ingest.late_grace_ms),
            max_laps_per_batch=li.get("maxLapsPerBatch", defaults.lap_ingest.max_laps_per_batch),
            min_inter_lap_ms=li.get("minInterLapMs", defaults.lap_ingest.min_inter_lap_ms),
        ),
        swim=SwimTuning(
            auto_inactivity_timeout_seconds=sw.get("autoInactivityTimeoutSeconds", defaults.swim.auto_inactivity_timeout_seconds),
            default_lane_count=sw.get("defaultLaneCount", defaults.swim.default_lane_count),
            max_lane_count=sw.get("maxLaneCount", defaults.swim.max_lane_count),
        ),
        auth=AuthTuning(
            token_ttl_hours=au.get("tokenTtlHours", defaults.auth.token_ttl_hours),
            max_failed_attempts=au.get("maxFailedAttempts", defaults.auth.max_failed_attempts),
            lockout_minutes=au.get("lockoutMinutes", defaults.auth.lockout_minutes),
        ),
        reference=ReferenceTuning(
            base_lap_ms=ref.get("baseLapMs", defaults.reference.base_lap_ms),
            variation_ms=ref.get("variationMs", defaults.reference.variation_ms),
            failure_rate=ref.get("failureRate", defaults.reference.failure_rate),
        ),
    )


TUNING: Tuning = _load()
