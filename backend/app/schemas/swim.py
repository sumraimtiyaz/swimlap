"""Swim DTOs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import ClosureMethod, SwimStatus


class CreateSwimRequest(BaseModel):
    venue_id: int
    swimmer_id: int
    lane_no: int = Field(ge=1)
    scheduled_start: datetime
    lap_target: int | None = Field(default=None, ge=1, le=500)


class AssignRequest(BaseModel):
    swim_id: int
    timer_id: int


class SwimOut(BaseModel):
    id: int
    venue_id: int
    swimmer_id: int
    lane_no: int
    scheduled_start: datetime
    lap_target: int | None
    status: SwimStatus
    closure_method: ClosureMethod | None = None
    closed_at: datetime | None = None
    # Display enrichment (filled by the presenter).
    swimmer_name: str = ""
    venue_name: str = ""


class SwimDetailOut(SwimOut):
    assigned_timer_id: int | None = None
    assigned_timer_name: str | None = None
    assignment_id: int | None = None


class StateOut(BaseModel):
    """Resume payload for the mobile app (PRD §6.8)."""

    swim_id: int
    status: SwimStatus
    lap_count: int
    last_seq: int
    recent_laps_ms: list[float] = []  # last three recorded lap times, most recent first
