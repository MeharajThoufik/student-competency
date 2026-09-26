"""Printable competency report (A4 PDF) for one learner."""

import io
import math
from datetime import UTC, datetime

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
GRID = colors.HexColor("#e2e8f0")
SERIES = colors.HexColor("#2a78d6")
TREND = {"emerging": "Emerging", "improving": "Improving", "stable": "Stable", "declining": "Declining", "inactive": "Not started"}
EVIDENCE = {"verified": "Verified", "evidence_attached": "Evidence attached", "self_reported": "Self-reported", "rejected": "Rejected"}
_REPLACE = {"−": "-", "→": "->", "≥": ">=", "≤": "<=", "✓": "", "±": "+/-"}


def clean(text: object) -> str:
    """The standard PDF fonts cover Windows-1252 only; replace anything else."""
    s = str(text)
    for a, b in _REPLACE.items():
        s = s.replace(a, b)
    s = s.encode("cp1252", errors="replace").decode("cp1252")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=ss["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=INK)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=10, textColor=MUTED),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=18, leading=22),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=10, spaceAfter=4),
        "right": ParagraphStyle("right", parent=base, alignment=TA_RIGHT),
    }


def signed(v: float) -> str:
    return "0.0" if abs(v) < 0.05 else f"{v:+.1f}"


def radar(labels: list[str], values: list[float], size: float = 62 * mm, width: float = 174 * mm) -> Drawing:
    d = Drawing(width, size + 14 * mm)
    cx, cy, r = d.width / 2, d.height / 2, size / 2 - 4 * mm
    n = len(values)
    angle = lambda i: math.pi / 2 - 2 * math.pi * i / n  # noqa: E731
    for level in (25, 50, 75, 100):
        pts = []
        for i in range(n):
            pts += [cx + r * level / 100 * math.cos(angle(i)), cy + r * level / 100 * math.sin(angle(i))]
        d.add(Polygon(pts, strokeColor=GRID, strokeWidth=0.6, fillColor=None))
    for i, label in enumerate(labels):
        x, y = cx + r * math.cos(angle(i)), cy + r * math.sin(angle(i))
        d.add(Line(cx, cy, x, y, strokeColor=GRID, strokeWidth=0.6))
        lx, ly = cx + (r + 5 * mm) * math.cos(angle(i)), cy + (r + 5 * mm) * math.sin(angle(i))
        anchor = "middle" if abs(lx - cx) < 3 else ("start" if lx > cx else "end")
        d.add(String(lx, ly - 3, clean(label).replace("&amp;", "&"), fontName="Helvetica", fontSize=7, fillColor=MUTED, textAnchor=anchor))
    pts = []
    for i, v in enumerate(values):
        pts += [cx + r * v / 100 * math.cos(angle(i)), cy + r * v / 100 * math.sin(angle(i))]
    fill = colors.Color(SERIES.red, SERIES.green, SERIES.blue, alpha=0.15)
    d.add(Polygon(pts, strokeColor=SERIES, strokeWidth=1.5, fillColor=fill))
    for i in range(n):
        d.add(Circle(pts[2 * i], pts[2 * i + 1], 2, fillColor=SERIES, strokeColor=colors.white, strokeWidth=0.8))
    return d


def _table(rows, widths, header=True, align_right=()):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED)]
    for col in align_right:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def build_report(profile, insights, academics, activities, generated_by: str | None = None) -> bytes:
    """profile: UserOut-like; insights: InsightsOut; academics: AcademicSummary; activities: ActivityOut list."""
    st = _styles()
    buf = io.BytesIO()
    now = datetime.now(UTC)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            18 * mm, 10 * mm,
            "Score = sum of weight x level x confidence x recency per activity, scaled to 0-100. "
            "Verified evidence counts x1.0, attached x0.8, self-reported x0.5.",
        )  # fmt: skip
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
        title=f"Competency report - {profile.name}", author="Competency Evolution Framework",
    )  # fmt: skip
    p = lambda text, style="base": Paragraph(clean(text) if style != "raw" else text, st["base" if style == "raw" else style])  # noqa: E731
    story = [
        p("Competency Report", "title"),
        p(" · ".join(x for x in [profile.name, profile.register_no, profile.programme, profile.batch] if x)),
        p(f"Scores as of {insights.as_of} · generated {now:%Y-%m-%d %H:%M} UTC" + (f" by {generated_by}" if generated_by else ""), "small"),
        Spacer(1, 4 * mm),
    ]

    verified = sum(a.evidence_status == "verified" for a in activities)
    with_evidence = sum(a.evidence_status in ("verified", "evidence_attached") for a in activities)
    summary = [
        ["Activities", "With evidence", "Verified", "CGPA", "Credits"],
        [str(len(activities)), str(with_evidence), str(verified), f"{academics.cgpa:.2f}" if academics.cgpa is not None else "-", f"{academics.total_credits:g}"],
    ]
    story += [_table(summary, [34 * mm] * 5, align_right=range(5)), Spacer(1, 2 * mm)]

    comps = insights.competencies
    if insights.activity_count:
        rows = [["Competency", "Score", f"{insights.window_months}-mo change", "Trend", "Percentile"]]
        for c in sorted(comps, key=lambda c: -c.score):
            rows.append(
                [
                    clean(c.label),
                    f"{c.score:.1f}",
                    signed(c.change),
                    TREND.get(c.trend, c.trend),
                    f"{c.percentile:.0f}" if c.percentile is not None else "-",
                ]
            )
        labels = {c.key: c.label for c in comps}
        story += [
            p("Competency profile", "h2"),
            radar([c.label for c in comps], [c.score for c in comps]),
            _table(rows, [54 * mm, 24 * mm, 32 * mm, 34 * mm, 30 * mm], align_right=(1, 2, 4)),
            Spacer(1, 2 * mm),
            p("Strengths: " + (", ".join(labels[k] for k in insights.strengths) or "none above 30 yet")),
            p("Gaps to work on: " + ", ".join(labels[k] for k in insights.gaps)),
            p(f"Percentiles compare with {insights.cohort_size} other learners.", "small") if insights.cohort_size else Spacer(1, 0),
        ]
        if insights.recommendations:
            story.append(p("Recommendations", "h2"))
            for r in insights.recommendations:
                story.append(p(f"<b>{clean(r.title)}</b> (up to +{r.gain:.1f}). {clean(r.detail)}", "raw"))
                story.append(Spacer(1, 1.5 * mm))
    else:
        story.append(p("No activities recorded yet, so no competency scores are available."))

    if activities:
        rows = [["Date", "Activity", "Type", "Outcome", "Evidence"]]
        for a in activities[:40]:
            rows.append([
                str(a.start_date), Paragraph(clean(a.title), st["base"]), clean(a.type.label),
                a.outcome.replace("_", " ").title(), EVIDENCE.get("rejected" if a.verification_status == "rejected" else a.evidence_status, ""),
            ])  # fmt: skip
        story += [p("Activities", "h2"), _table(rows, [20 * mm, 66 * mm, 34 * mm, 22 * mm, 32 * mm])]
        if len(activities) > 40:
            story.append(p(f"Showing the 40 most recent of {len(activities)} activities.", "small"))

    if academics.semesters:
        rows = [["Semester", "Credits", "SGPA"]] + [[str(s.semester), f"{s.credits:g}", f"{s.sgpa:.2f}"] for s in academics.semesters]
        rows.append(["CGPA", f"{academics.total_credits:g}", f"{academics.cgpa:.2f}"])
        t = _table(rows, [30 * mm, 25 * mm, 25 * mm], align_right=(1, 2))
        t.setStyle(TableStyle([("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 8.5)]))
        story += [KeepTogether([p("Academics", "h2"), t])]

    d = insights.interests
    if d.now or d.removed:
        story += [p("Interests", "h2"), p("Current: " + (", ".join(d.now) or "none"))]
        if d.drift is not None and d.since:
            story.append(p(f"Since {d.since:%Y-%m-%d}: {len(d.added)} added, {len(d.removed)} dropped (drift {100 * d.drift:.0f}%).", "small"))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
