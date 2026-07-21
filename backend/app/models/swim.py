"""Swim ORM model — one swimmer's practice swim: one swimmer, one lane, one timer, N laps."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SwimRow(Base):
    __tablename__ = "swims"

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False, index=True)
    swimmer_id: Mapped[int] = mapped_column(ForeignKey("swimmers.id"), nullable=False, index=True)
    lane_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lap_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled", index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
