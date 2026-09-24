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
    """Builds a short tailored-CV-highlights PDF for one job. Returns PDF bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleC", parent=styles["Title"], textColor=colors.HexColor("#4338ca"))
    subtitle_style = ParagraphStyle("SubtitleC", parent=styles["Normal"], textColor=colors.grey, spaceAfter=14)
    section_style = ParagraphStyle("SectionC", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)

    story = []
    story.append(Paragraph(_clean(profile.get("name", "Candidate")), title_style))
    story.append(Paragraph(
        f"Tailored for: {_clean(job.get('title', ''))} at {_clean(job.get('company', ''))}",
        subtitle_style,
    ))

    story.append(Paragraph("Highlights for this role", section_style))
    highlights = tailored.get("cv_highlights", [])
    if highlights:
        items = [ListItem(Paragraph(_clean(h), styles["Normal"])) for h in highlights]
        story.append(ListFlowable(items, bulletType="bullet"))

    story.append(Paragraph("Education", section_style))
    for edu in profile.get("education", []):
        line = f"{_clean(edu.get('degree', ''))}, {_clean(edu.get('institution', ''))} ({_clean(edu.get('dates', ''))})"
        story.append(Paragraph(line, styles["Normal"]))

    story.append(Paragraph("Skills", section_style))
    story.append(Paragraph(_clean(", ".join(profile.get("skills", []))), styles["Normal"]))

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
