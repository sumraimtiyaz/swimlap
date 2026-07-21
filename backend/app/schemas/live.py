"""Live-view DTOs (PRD §8.3)."""
from __future__ import annotations

from pydantic import BaseModel


class LiveRowOut(BaseModel):
    swim_id: int
    swimmer_name: str
    venue_name: str
    lane_no: int
    timer_id: int | None
    timer_name: str | None
    connected: bool          # presence — is the app connected right now?
    lap_count: int           # capturing — how many valid laps so far
    last_lap_ms: float | None
    stalled: bool            # lap count hasn't moved for > 2x typical lap time
