from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    label: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class MappingWeight(Base):
    """W[activity type, competency]: how strongly an activity type develops a competency (0–1)."""

    __tablename__ = "mapping_weights"

    activity_type_id: Mapped[int] = mapped_column(ForeignKey("activity_types.id", ondelete="CASCADE"), primary_key=True)
    competency_id: Mapped[int] = mapped_column(ForeignKey("competencies.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float)


class CompetencySnapshot(Base):
    """Immutable record of a learner's competency vector, written on every change (event sourcing)."""

    __tablename__ = "competency_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    scores: Mapped[dict[str, float]] = mapped_column(JSONType)
    # activity_created | activity_updated | activity_deleted | evidence_added | evidence_removed | recompute | synthetic
    trigger: Mapped[str] = mapped_column(String(30))
    activity_id: Mapped[int | None] = mapped_column(Integer)  # not a FK: the activity may later be deleted
