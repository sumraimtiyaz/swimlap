"""Reference lap ORM model — comparison timing (simulated today; swappable later)."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ReferenceLapRow(Base):
    __tablename__ = "reference_laps"
    __table_args__ = (UniqueConstraint("swim_id", "lap_no", name="uq_reference_swim_lapno"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    swim_id: Mapped[int] = mapped_column(ForeignKey("swims.id", ondelete="CASCADE"), index=True, nullable=False)
    lap_no: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
