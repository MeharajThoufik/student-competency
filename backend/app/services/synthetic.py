"""Synthetic learner generator for demos and evaluation.

Each persona has a known, intended trajectory, so later phases can check whether the
trend detection and clustering recover it (ground truth = users.synthetic_persona):

    coder        steadily rising Technical and Problem-Solving
    leader       rising Leadership, Communication and Collaboration
    researcher   little activity in year 1, then Research emerges in year 2
    all_rounder  constant mixed activity, so scores plateau (stable)
    fading       very active early, almost inactive after ~10 months (declining)

Generation is deterministic for a given seed.
"""

import hashlib
import math
import random
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AcademicRecord, Activity, ActivityType, CompetencySnapshot, EvidenceFile, Interest, Skill, User
from app.services.competency import Framework, load_framework
from app.services.scoring import ActivityInput, compute_scores, score_vector


@dataclass(frozen=True)
class Persona:
    key: str
    share: float
    rate: Callable[[int], float]  # expected activities in month m (0-based)
    types: Callable[[int], dict[str, float]]  # activity-type mix in month m
    grade_bias: float
    skills: tuple[str, ...]
    interests: Callable[[int], tuple[str, ...]]  # active interests in month m


def _mix(**w: float) -> dict[str, float]:
    return w


PERSONAS: list[Persona] = [
    Persona(
        "coder",
        0.25,
        rate=lambda m: 0.5 + 0.7 * m / 23,
        types=lambda m: _mix(project=0.35, hackathon=0.15, certification=0.2, online_course=0.15, competition=0.15),
        grade_bias=0.3,
        skills=("Python", "JavaScript", "React", "Docker", "SQL", "AWS", "Git", "Data Structures"),
        interests=lambda m: ("Web Development", "Algorithms") if m < 12 else ("Cloud Computing", "DevOps", "Algorithms"),
    ),
    Persona(
        "leader",
        0.20,
        rate=lambda m: 0.5 + 0.4 * m / 23,
        types=lambda m: _mix(club_role=0.3, event_organizing=0.3, volunteering=0.2, workshop=0.1, project=0.1),
        grade_bias=0.0,
        skills=("Public Speaking", "Team Management", "Event Planning", "Negotiation", "Excel"),
        interests=lambda m: ("Entrepreneurship", "Social Impact", "Management"),
    ),
    Persona(
        "researcher",
        0.15,
        rate=lambda m: 0.2 if m < 12 else 0.9,
        types=lambda m: _mix(online_course=0.5, workshop=0.5)
        if m < 12
        else _mix(paper=0.4, internship=0.1, workshop=0.2, project=0.2, online_course=0.1),
        grade_bias=0.5,
        skills=("Python", "Machine Learning", "Statistics", "LaTeX", "Literature Review"),
        interests=lambda m: ("Machine Learning",) if m < 12 else ("Machine Learning", "Research", "Blockchain"),
    ),
    Persona(
        "all_rounder",
        0.25,
        rate=lambda m: 0.8,
        types=lambda m: {k: 1.0 for k in ("project", "certification", "hackathon", "workshop", "club_role", "event_organizing", "competition", "volunteering")},
        grade_bias=0.2,
        skills=("Python", "Communication", "Teamwork", "Java", "Design Thinking"),
        interests=lambda m: ("Technology", "Sports", "Music"),
    ),
    Persona(
        "fading",
        0.15,
        rate=lambda m: 1.0 if m < 10 else 0.05,
        types=lambda m: _mix(project=0.3, certification=0.3, online_course=0.2, hackathon=0.2),
        grade_bias=-0.4,
        skills=("C", "HTML", "CSS", "Python"),
        interests=lambda m: ("Gaming", "Web Development") if m < 10 else ("Gaming",),
    ),
]
PERSONA_KEYS = [p.key for p in PERSONAS]

# Plausible outcome per activity type: (outcome, probability)
OUTCOMES: dict[str, list[tuple[str, float]]] = {
    "project": [("contributor", 0.6), ("lead", 0.4)],
    "certification": [("completed", 1.0)],
    "online_course": [("completed", 1.0)],
    "hackathon": [("participant", 0.6), ("finalist", 0.25), ("winner", 0.15)],
    "competition": [("participant", 0.6), ("finalist", 0.25), ("winner", 0.15)],
    "workshop": [("participant", 1.0)],
    "internship": [("contributor", 1.0)],
    "paper": [("contributor", 0.5), ("lead", 0.5)],
    "club_role": [("contributor", 0.4), ("lead", 0.6)],
    "event_organizing": [("contributor", 0.5), ("lead", 0.5)],
    "volunteering": [("participant", 0.6), ("contributor", 0.4)],
    "award": [("winner", 1.0)],
}
SCOPES = [("personal", 0.1), ("institute", 0.5), ("state", 0.15), ("national", 0.2), ("international", 0.05)]
DURATION_DAYS: dict[str, tuple[int, int]] = {
    "project": (14, 120),
    "online_course": (14, 60),
    "internship": (60, 180),
    "club_role": (120, 300),
    "paper": (30, 120),
    "volunteering": (1, 60),
}
EVIDENCE = [("self_reported", 0.35), ("evidence_attached", 0.45), ("verified", 0.20)]
TITLES: dict[str, list[str]] = {
    "project": ["Campus Navigator App", "Expense Tracker", "IoT Weather Station", "Chatbot for FAQs", "Portfolio Website", "Library System"],
    "certification": ["AWS Cloud Practitioner", "Google Data Analytics", "Azure Fundamentals", "Oracle Java SE", "CCNA"],
    "online_course": ["Machine Learning (Coursera)", "DSA in Python (NPTEL)", "Cloud Computing (NPTEL)", "Deep Learning Specialization"],
    "hackathon": ["Smart India Hackathon", "HackMIT", "Code for Good", "ETHIndia", "Campus Hack Night"],
    "competition": ["CodeChef Starters", "ICPC Regionals", "Quiz Fest", "Design Sprint Challenge"],
    "workshop": ["Blockchain Workshop", "Kubernetes Bootcamp", "Research Methodology Seminar", "UI/UX Workshop"],
    "internship": ["Summer Internship at TCS", "Research Intern, IIT Madras", "Cloud Intern at Zoho"],
    "paper": ["Survey on Federated Learning", "Blockchain for Academic Records", "Edge AI for Agriculture"],
    "club_role": ["Coding Club Secretary", "IEEE Student Branch Chair", "Music Club Coordinator"],
    "event_organizing": ["Tech Fest Coordinator", "Orientation Volunteer Lead", "Alumni Meet Organizer"],
    "volunteering": ["NSS Blood Donation Camp", "Teach for Village Schools", "Beach Clean-up Drive"],
    "award": ["Merit Scholarship", "Best Outgoing Student", "Dean's List"],
}
FIRST = ["Aarav", "Diya", "Karthik", "Meera", "Rahul", "Ananya", "Vikram", "Priya", "Arjun", "Kavya", "Surya", "Nila", "Rohan", "Isha", "Harish", "Lakshmi", "Varun", "Sneha", "Farhan", "Divya"]
LAST = ["K", "S", "R", "M", "P", "N", "V", "A", "T", "J"]
COURSES = [("CSC101", "Programming in C"), ("MAT102", "Discrete Mathematics"), ("CSC103", "Data Structures"), ("CSC104", "Computer Networks"), ("CSC105", "Operating Systems"), ("CSC201", "Cloud Computing"), ("CSC202", "Blockchain Technology"), ("CSC203", "Machine Learning"), ("CSC204", "Distributed Systems"), ("CSC205", "Research Methodology")]
GRADES = ["O", "A+", "A", "B+", "B", "C"]


def _pick(rng: random.Random, options: list[tuple[str, float]] | dict[str, float]) -> str:
    items = list(options.items()) if isinstance(options, dict) else options
    return rng.choices([k for k, _ in items], weights=[w for _, w in items])[0]


def _poisson(rng: random.Random, lam: float) -> int:
    # Knuth's algorithm; lam is small (< 2)
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _at(d: date) -> datetime:
    return datetime.combine(d, time(12), tzinfo=UTC)


def delete_synthetic(db: Session) -> int:
    n = db.scalar(select(func.count()).select_from(User).where(User.synthetic_persona.is_not(None))) or 0
    db.execute(delete(User).where(User.synthetic_persona.is_not(None)))
    db.commit()
    return n


def synthetic_summary(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(User.synthetic_persona, func.count()).where(User.synthetic_persona.is_not(None)).group_by(User.synthetic_persona)
    )
    return {k: n for k, n in rows}


def generate(db: Session, learners: int = 200, seed: int = 42, months: int = 24, end: date | None = None) -> dict[str, int]:
    """Replace all synthetic learners with a fresh deterministic set. Returns learners per persona."""
    rng = random.Random(seed)
    end = end or date.today()
    start = end - timedelta(days=round(months * 30.4375))
    delete_synthetic(db)

    fw = load_framework(db)
    types = {t.key: t for t in db.scalars(select(ActivityType))}
    counts: Counter[str] = Counter()

    for i in range(1, learners + 1):
        persona = rng.choices(PERSONAS, weights=[p.share for p in PERSONAS])[0]
        counts[persona.key] += 1
        tag = f"{i:04d}"
        user = User(
            firebase_uid=f"synthetic-{tag}",
            email=f"synthetic-{tag}@example.invalid",
            name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            role="learner",
            register_no=f"RA24SYN{tag}",
            programme=rng.choice(["M.Tech Cloud Computing", "M.Tech Data Science", "B.Tech CSE"]),
            department="Computing Technologies",
            batch=f"{start.year}-{start.year + 2}",
            consent_given_at=_at(start),
            synthetic_persona=persona.key,
            created_at=_at(start),
        )
        db.add(user)
        db.flush()

        _academics(db, rng, user, persona)
        _skills_and_interests(db, rng, user, persona, start, months)
        activities = _activities(db, rng, user, persona, start, end, months, types)
        db.flush()
        _replay_snapshots(db, user, activities, fw, end)

    db.commit()
    return dict(counts)


def _academics(db: Session, rng: random.Random, user: User, persona: Persona) -> None:
    for sem in range(1, 5):
        for code, name in rng.sample(COURSES, 5):
            idx = min(len(GRADES) - 1, max(0, round(rng.gauss(2.0 - persona.grade_bias * 2, 1.0))))
            db.add(AcademicRecord(user_id=user.id, semester=sem, course_code=code, course_name=name, credits=rng.choice([3, 4]), grade=GRADES[idx]))


def _skills_and_interests(db: Session, rng: random.Random, user: User, persona: Persona, start: date, months: int) -> None:
    for name in rng.sample(persona.skills, k=min(len(persona.skills), rng.randint(3, 6))):
        category = "soft" if name in {"Public Speaking", "Team Management", "Negotiation", "Communication", "Teamwork"} else "technical"
        db.add(Skill(user_id=user.id, name=name, category=category, self_level=rng.randint(2, 5)))

    # Interest history: an interest is added when it first appears and removed when it disappears.
    active: dict[str, Interest] = {}
    for m in range(months):
        current = set(persona.interests(m))
        when = _at(start + timedelta(days=round(m * 30.4375)))
        for tag in current - active.keys():
            active[tag] = Interest(user_id=user.id, tag=tag, level=rng.randint(3, 5), created_at=when)
            db.add(active[tag])
        for tag in active.keys() - current:
            active.pop(tag).removed_at = when


def _activities(
    db: Session, rng: random.Random, user: User, persona: Persona, start: date, end: date, months: int, types: dict[str, ActivityType]
) -> list[tuple[Activity, str]]:
    out: list[tuple[Activity, str]] = []
    for m in range(months):
        for _ in range(_poisson(rng, persona.rate(m))):
            type_key = _pick(rng, persona.types(m))
            day = start + timedelta(days=round((m + rng.random()) * 30.4375))
            if day >= end:
                continue
            lo, hi = DURATION_DAYS.get(type_key, (0, 2))
            end_day = day + timedelta(days=rng.randint(lo, hi)) if hi > 2 else None
            evidence = _pick(rng, EVIDENCE)
            activity = Activity(
                user_id=user.id,
                type_id=types[type_key].id,
                title=rng.choice(TITLES[type_key]),
                organization=None,
                start_date=day,
                end_date=min(end_day, end) if end_day else None,
                outcome=_pick(rng, OUTCOMES[type_key]),
                scope="personal" if type_key == "online_course" else _pick(rng, SCOPES),
                skills=rng.sample(persona.skills, k=min(2, len(persona.skills))),
                verification_status="verified" if evidence == "verified" else "unverified",
                verified_at=_at(day + timedelta(days=7)) if evidence == "verified" else None,
                created_at=_at(day),
            )
            if evidence != "self_reported":
                digest = hashlib.sha256(f"{user.id}-{m}-{rng.random()}".encode()).hexdigest()
                # Placeholder row only: no file is stored, so downloads return 404.
                activity.evidence = [
                    EvidenceFile(
                        storage_key=f"synthetic/{uuid.UUID(int=rng.getrandbits(128)).hex}.pdf",
                        filename="certificate.pdf",
                        content_type="application/pdf",
                        size_bytes=rng.randint(80_000, 900_000),
                        sha256=digest,
                        uploaded_at=_at(day),
                    )
                ]
            db.add(activity)
            out.append((activity, type_key))
    return out


def _replay_snapshots(db: Session, user: User, activities: list[tuple[Activity, str]], fw: Framework, end: date) -> None:
    """One snapshot per activity, scored as of the day it was added, plus one for today."""
    inputs = [
        ActivityInput(
            id=a.id,
            title=a.title,
            type_key=type_key,
            start_date=a.start_date,
            end_date=a.end_date,
            outcome=a.outcome,
            scope=a.scope,
            confidence_key="verified" if a.verification_status == "verified" else ("evidence_attached" if a.evidence else "self_reported"),
        )
        for a, type_key in activities
    ]
    for inp in sorted(inputs, key=lambda x: x.start_date):
        scores = compute_scores(inputs, fw.weights, fw.keys, inp.start_date)
        db.add(CompetencySnapshot(user_id=user.id, taken_at=_at(inp.start_date), scores=score_vector(scores), trigger="synthetic", activity_id=inp.id))
    db.add(
        CompetencySnapshot(
            user_id=user.id, taken_at=_at(end), scores=score_vector(compute_scores(inputs, fw.weights, fw.keys, end)), trigger="synthetic"
        )
    )
