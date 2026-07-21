"""Lap ingestion DTOs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import LapSource, SwimStatus


class LapIn(BaseModel):
    seq: int = Field(ge=0)
    device_mono_ms: float
    device_ts: datetime | None = None
    was_buffered: bool = False
    source: LapSource = LapSource.MANUAL


class SubmitLapsRequest(BaseModel):
    # The offline queue flushes in one request, each capture keeping its own seq
    # and timestamps. timer_id comes from the token; swim_id from the path.
    laps: list[LapIn] = Field(min_length=1, max_length=500)


class LapOutcomeOut(BaseModel):
    seq: int
    status: str
    is_valid: bool
    was_late: bool
    was_buffered: bool
    reasons: list[str] = []


class SubmitLapsResponse(BaseModel):
    outcomes: list[LapOutcomeOut]
    valid_lap_count: int
    swim_status: SwimStatus
    went_live: bool
