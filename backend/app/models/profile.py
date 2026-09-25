from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# SRM 10-point grading scale.
GRADE_POINTS: dict[str, int] = {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "F": 0, "Ab": 0}


class AcademicRecord(TimestampMixin, Base):
    __tablename__ = "academic_records"
    __table_args__ = (UniqueConstraint("user_id", "semester", "course_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    semester: Mapped[int] = mapped_column(Integer)
    course_code: Mapped[str] = mapped_column(String(30))
    course_name: Mapped[str] = mapped_column(String(200))
    credits: Mapped[float] = mapped_column(Float)
    grade: Mapped[str] = mapped_column(String(4))


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20))  # technical | soft | domain | tool
    self_level: Mapped[int] = mapped_column(Integer)  # 1–5


class Interest(Base):
    """Interests are soft-deleted (removed_at) so interest drift can be analysed over time."""

    __tablename__ = "interests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tag: Mapped[str] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(Integer)  # 1–5
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
