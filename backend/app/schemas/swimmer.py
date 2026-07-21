"""Swimmer DTOs."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSwimmerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class SwimmerOut(BaseModel):
    id: int
    name: str
