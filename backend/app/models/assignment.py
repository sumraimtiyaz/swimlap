"""Assignment ORM model — a timer (user) assigned to a swim."""
from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AssignmentRow(Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("swim_id", "timer_id", name="uq_assignment_swim_timer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    swim_id: Mapped[int] = mapped_column(ForeignKey("swims.id", ondelete="CASCADE"), index=True, nullable=False)
    timer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
