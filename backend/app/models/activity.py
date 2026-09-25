from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin


class ActivityType(Base):
    __tablename__ = "activity_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    label: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("activity_types.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    organization: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    outcome: Mapped[str] = mapped_column(String(20))  # participant | contributor | lead | completed | finalist | winner
    scope: Mapped[str] = mapped_column(String(20))  # personal | institute | state | national | international
    skills: Mapped[list[str]] = mapped_column(JSONType, default=list)
    url: Mapped[str | None] = mapped_column(String(500))
    # Educator review (P4): unverified | verified | rejected
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)

    type: Mapped[ActivityType] = relationship(lazy="joined")
    evidence: Mapped[list["EvidenceFile"]] = relationship(
        back_populates="activity", cascade="all, delete-orphan", order_by="EvidenceFile.id", lazy="selectin"
    )

    @property
    def evidence_status(self) -> str:
        """self_reported → evidence_attached → verified; drives the confidence weight in P2 scoring."""
        if self.verification_status == "verified":
            return "verified"
        return "evidence_attached" if self.evidence else "self_reported"


class EvidenceFile(Base):
    __tablename__ = "evidence_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    activity: Mapped[Activity] = relationship(back_populates="evidence")
