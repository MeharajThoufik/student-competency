from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models.profile import GRADE_POINTS


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- User ----------
class UserOut(ORM):
    id: int
    email: str
    name: str
    role: str
    register_no: str | None
    programme: str | None
    department: str | None
    batch: str | None
    bio: str | None
    career_goals: str | None
    consent_given_at: datetime | None


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    register_no: str | None = Field(None, max_length=50)
    programme: str | None = Field(None, max_length=200)
    department: str | None = Field(None, max_length=200)
    batch: str | None = Field(None, max_length=20)
    bio: str | None = Field(None, max_length=2000)
    career_goals: str | None = Field(None, max_length=2000)


# ---------- Academics ----------
Grade = Literal["O", "A+", "A", "B+", "B", "C", "F", "Ab"]


class AcademicIn(BaseModel):
    semester: int = Field(ge=1, le=12)
    course_code: str = Field(min_length=1, max_length=30)
    course_name: str = Field(min_length=1, max_length=200)
    credits: float = Field(gt=0, le=30)
    grade: Grade


class AcademicOut(ORM, AcademicIn):
    id: int


class SemesterSummary(BaseModel):
    semester: int
    credits: float
    sgpa: float


class AcademicSummary(BaseModel):
    semesters: list[SemesterSummary]
    cgpa: float | None
    total_credits: float


def grade_point(grade: str) -> int:
    return GRADE_POINTS[grade]


# ---------- Skills & interests ----------
class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: Literal["technical", "soft", "domain", "tool"]
    self_level: int = Field(ge=1, le=5)

    @field_validator("name")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class SkillOut(ORM, SkillIn):
    id: int


class InterestIn(BaseModel):
    tag: str = Field(min_length=1, max_length=100)
    level: int = Field(ge=1, le=5)

    @field_validator("tag")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class InterestOut(ORM, InterestIn):
    id: int
    created_at: datetime


# ---------- Activities ----------
Outcome = Literal["participant", "contributor", "lead", "completed", "finalist", "winner"]
Scope = Literal["personal", "institute", "state", "national", "international"]


class ActivityTypeOut(ORM):
    id: int
    key: str
    label: str
    description: str | None


class ActivityIn(BaseModel):
    type_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    organization: str | None = Field(None, max_length=200)
    start_date: date
    end_date: date | None = None
    outcome: Outcome
    scope: Scope
    skills: list[str] = Field(default_factory=list, max_length=20)
    url: HttpUrl | None = None

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, v: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for s in (x.strip() for x in v):
            if s and s.lower() not in seen:
                seen[s.lower()] = s[:60]
        return list(seen.values())

    @model_validator(mode="after")
    def check_dates(self) -> "ActivityIn":
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.start_date > date.today():
            raise ValueError("start_date cannot be in the future")
        return self


class EvidenceOut(ORM):
    id: int
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    uploaded_at: datetime


class ActivityOut(ORM):
    id: int
    type: ActivityTypeOut
    title: str
    description: str | None
    organization: str | None
    start_date: date
    end_date: date | None
    outcome: str
    scope: str
    skills: list[str]
    url: str | None
    verification_status: str
    evidence_status: str
    review_note: str | None
    evidence: list[EvidenceOut]
    created_at: datetime
    updated_at: datetime
