"""
Generates downloadable PDF files for a tailored CV (highlights) and cover
letter, for a given approved job. Uses reportlab, kept in memory (BytesIO)
so Streamlit can offer them directly as downloads without writing to disk.
"""

from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem


def _clean(text: str) -> str:
    """Reportlab's core fonts are Latin-1; swap smart quotes/dashes that
    sometimes come back from the model and would otherwise raise errors."""
    if not text:
        return ""
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def generate_cv_pdf(profile: dict, tailored: dict, job: dict) -> bytes:
    """Builds a full, real CV (not just a highlights excerpt) tailored for one job.
    Includes name, a tailored highlights section, full experience, education,
    skills and certifications — everything drawn from the real profile,
    nothing invented. Returns PDF bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleC", parent=styles["Title"], textColor=colors.HexColor("#4338ca"), spaceAfter=2)
    subtitle_style = ParagraphStyle("SubtitleC", parent=styles["Normal"], textColor=colors.grey, spaceAfter=14)
    section_style = ParagraphStyle("SectionC", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6,
                                    textColor=colors.HexColor("#1A2332"))
    role_style = ParagraphStyle("RoleC", parent=styles["Normal"], fontName="Helvetica-Bold", spaceBefore=8)
    meta_style = ParagraphStyle("MetaC", parent=styles["Normal"], textColor=colors.grey, fontSize=9, spaceAfter=4)

    story = []
    story.append(Paragraph(_clean(profile.get("name", "Candidate")), title_style))
    story.append(Paragraph(
        f"Application for: {_clean(job.get('title', ''))} at {_clean(job.get('company', ''))}",
        subtitle_style,
    ))

    # --- tailored highlights: the pitch specific to this job ---
    highlights = tailored.get("cv_highlights", [])
    if highlights:
        story.append(Paragraph("Profile Highlights for This Role", section_style))
        items = [ListItem(Paragraph(_clean(h), styles["Normal"])) for h in highlights]
        story.append(ListFlowable(items, bulletType="bullet"))

    # --- full real work experience, not just the highlights excerpt ---
    experience = profile.get("experience", [])
    if experience:
        story.append(Paragraph("Experience", section_style))
        for exp in experience:
            role_line = f"{_clean(exp.get('role', ''))}, {_clean(exp.get('company', ''))}"
            story.append(Paragraph(role_line, role_style))
            if exp.get("dates"):
                story.append(Paragraph(_clean(exp.get("dates", "")), meta_style))
            exp_highlights = exp.get("highlights", [])
            if exp_highlights:
                items = [ListItem(Paragraph(_clean(h), styles["Normal"])) for h in exp_highlights]
                story.append(ListFlowable(items, bulletType="bullet"))

    # --- education ---
    education = profile.get("education", [])
    if education:
        story.append(Paragraph("Education", section_style))
        for edu in education:
            line = f"{_clean(edu.get('degree', ''))}, {_clean(edu.get('institution', ''))}"
            story.append(Paragraph(f"<b>{line}</b>", styles["Normal"]))
            if edu.get("dates"):
                story.append(Paragraph(_clean(edu.get("dates", "")), meta_style))

    # --- skills ---
    skills = profile.get("skills", [])
    if skills:
        story.append(Paragraph("Skills", section_style))
        story.append(Paragraph(_clean(", ".join(skills)), styles["Normal"]))

    # --- certifications ---
    certs = profile.get("certifications", [])
    if certs:
        story.append(Paragraph("Certifications", section_style))
        story.append(Paragraph(_clean(", ".join(certs)), styles["Normal"]))

    doc.build(story)
    buf.seek(0)
    return buf.read()


def generate_cover_letter_pdf(cover_letter_text: str, profile: dict, job: dict) -> bytes:
    """Builds a simple cover-letter PDF for one job. Returns PDF bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=1 * inch, bottomMargin=1 * inch)
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle("HeaderCL", parent=styles["Normal"], textColor=colors.grey, spaceAfter=20)
    body_style = ParagraphStyle("BodyCL", parent=styles["Normal"], spaceAfter=12, leading=16)

    story = []
    story.append(Paragraph(_clean(profile.get("name", "Candidate")), styles["Heading2"]))
    story.append(Paragraph(
        f"Application for {_clean(job.get('title', ''))} at {_clean(job.get('company', ''))}",
        header_style,
    ))

    for para in cover_letter_text.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(_clean(para), body_style))

    doc.build(story)
    buf.seek(0)
    return buf.read()
