"""Lap ORM model — every confirmed timer capture (append-only).

The UNIQUE(timer_id, swim_id, seq) makes the database itself enforce idempotency:
even a race between two concurrent uploads of the same buffered lap collapses to
one row. The service checks first (fast path); this constraint is the backstop.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LapRow(Base):
    __tablename__ = "laps"
    __table_args__ = (UniqueConstraint("timer_id", "swim_id", "seq", name="uq_lap_timer_swim_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    swim_id: Mapped[int] = mapped_column(ForeignKey("swims.id", ondelete="CASCADE"), index=True, nullable=False)
    timer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    device_mono_ms: Mapped[float] = mapped_column(Float, nullable=False)
    server_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    device_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    was_buffered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    was_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    reasons: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
