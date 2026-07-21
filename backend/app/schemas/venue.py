"""Venue DTOs."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateVenueRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    lane_count: int = Field(ge=1, le=64)


class VenueOut(BaseModel):
    id: int
    name: str
    lane_count: int
