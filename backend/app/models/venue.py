"""Venue ORM model — swimming pool / location."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VenueRow(Base):
    __tablename__ = "venues"
    __table_args__ = (CheckConstraint("lane_count > 0", name="ck_venue_lane_count_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    lane_count: Mapped[int] = mapped_column(Integer, nullable=False)
