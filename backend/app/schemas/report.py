"""Report DTOs (PRD §10)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.domain.enums import SwimStatus


class ReportLapOut(BaseModel):
    lap_no: int
    seq: int
    recorded_ms: float | None
    cumulative_ms: float | None
    reference_ms: int | None
    deviation_ms: float | None
    derived: bool
    was_late: bool
    is_valid: bool
    note: str


class ReportSummaryOut(BaseModel):
    laps_recorded: int
    average_deviation_ms: float | None
    largest_deviation_ms: float | None
    largest_deviation_lap: int | None
    laps_without_comparison: int
    late_count: int
    comparable: bool


class ReportOut(BaseModel):
    swim_id: int
    swimmer_name: str
    venue_name: str
    lane_no: int
    status: SwimStatus
    scheduled_start: datetime
    simulated: bool
    banner: str
    laps: list[ReportLapOut]
    summary: ReportSummaryOut
