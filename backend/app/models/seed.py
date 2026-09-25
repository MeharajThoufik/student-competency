# Activity types offered in the Add Activity form. Competency weights per type are added in P2.
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
