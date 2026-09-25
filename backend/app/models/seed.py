# Activity types offered in the Add Activity form.
ACTIVITY_TYPES: list[tuple[str, str, str]] = [
    ("project", "Project", "Academic or personal project"),
    ("certification", "Certification", "Professional or online certification"),
    ("online_course", "Online Course", "MOOC or self-paced course"),
    ("hackathon", "Hackathon", "Time-boxed build competition"),
    ("competition", "Competition", "Coding, quiz, design or other contest"),
    ("workshop", "Workshop / Seminar", "Attended workshop, bootcamp or seminar"),
    ("internship", "Internship", "Industry or research internship"),
    ("paper", "Paper / Publication", "Research paper, poster or article"),
    ("club_role", "Club / Leadership Role", "Office bearer or coordinator role"),
    ("event_organizing", "Event Organizing", "Organized or volunteered at an event"),
    ("volunteering", "Community Service", "Volunteering or social initiative"),
    ("award", "Award / Recognition", "Scholarship, award or honour"),
]

# The 8 competency dimensions (key, label, description).
COMPETENCIES: list[tuple[str, str, str]] = [
    ("technical", "Technical", "Applying tools, programming and domain technologies to build working solutions."),
    ("problem_solving", "Problem-Solving", "Analysing problems and designing effective solutions under constraints."),
    ("communication", "Communication", "Explaining ideas clearly in writing, presentations and discussion."),
    ("leadership", "Leadership", "Taking responsibility, guiding others and driving initiatives."),
    ("collaboration", "Collaboration", "Working effectively in teams and with diverse people."),
    ("creativity", "Creativity", "Generating original ideas and novel approaches."),
    ("research", "Research", "Investigating questions systematically and producing new knowledge."),
    ("continuous_learning", "Continuous Learning", "Independently acquiring new knowledge and skills over time."),
]

# W[activity type][competency], expert-defined (0–1). Editable by admins (P4); tested for robustness
# with ±20% perturbation in the sensitivity analysis (P5).
#                    tech  prob  comm  lead  collab crea  resr  learn
_MATRIX: dict[str, tuple[float, ...]] = {
    "project":          (0.9, 0.7, 0.2, 0.2, 0.4, 0.6, 0.3, 0.3),
    "certification":    (0.7, 0.2, 0.0, 0.0, 0.0, 0.0, 0.1, 0.9),
    "online_course":    (0.6, 0.2, 0.0, 0.0, 0.0, 0.1, 0.1, 0.8),
    "hackathon":        (0.7, 0.9, 0.3, 0.3, 0.8, 0.8, 0.1, 0.3),
    "competition":      (0.5, 0.9, 0.2, 0.1, 0.2, 0.4, 0.1, 0.3),
    "workshop":         (0.4, 0.2, 0.2, 0.0, 0.3, 0.2, 0.2, 0.7),
    "internship":       (0.8, 0.6, 0.6, 0.3, 0.7, 0.3, 0.3, 0.5),
    "paper":            (0.5, 0.5, 0.6, 0.1, 0.3, 0.4, 1.0, 0.4),
    "club_role":        (0.1, 0.3, 0.7, 0.9, 0.7, 0.3, 0.0, 0.2),
    "event_organizing": (0.1, 0.4, 0.7, 0.7, 0.8, 0.4, 0.0, 0.1),
    "volunteering":     (0.0, 0.2, 0.6, 0.3, 0.8, 0.2, 0.0, 0.2),
    "award":            (0.4, 0.4, 0.2, 0.3, 0.2, 0.3, 0.3, 0.3),
}  # fmt: skip

MAPPING_WEIGHTS: dict[str, dict[str, float]] = {
    t: {c[0]: w for c, w in zip(COMPETENCIES, row, strict=True)} for t, row in _MATRIX.items()
}
