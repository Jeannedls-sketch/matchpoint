"""
Edits the candidate's REAL uploaded CV (.docx) in place for one job — finds
each proposed bullet's exact text and replaces it, keeping the original
file's fonts, sizes, and layout, instead of generating a fresh document
from scratch. Mirrors the "edit the real file, don't rewrite it" approach.
"""

from io import BytesIO
from docx import Document


def _replace_in_paragraph(paragraph, find: str, replace: str) -> bool:
    """
    Replaces `find` with `replace` inside one paragraph if the paragraph's
    full text matches (or contains) it, while preserving the formatting of
    the first run so the edit doesn't look out of place. Returns True if a
    replacement was made.
    """
    full_text = paragraph.text
    if find not in full_text:
        return False

    new_text = full_text.replace(find, replace, 1)

    if not paragraph.runs:
        return False

    # keep the first run's formatting (font, size, bold, etc.), put the
    # whole new text there, and clear any other runs in the paragraph so
    # the text isn't duplicated
    paragraph.runs[0].text = new_text
    for run in paragraph.runs[1:]:
        run.text = ""
    return True


def edit_cv_docx(original_bytes: bytes, edits: list) -> tuple:
    """
    Applies a list of {"find": ..., "replace": ...} edits to the real CV
    .docx file (searching paragraphs and table cells), preserving the
    original formatting. Returns (edited_bytes, applied_count).

    Edits whose "find" text isn't found verbatim are silently skipped
    (the model may occasionally propose text that doesn't match exactly -
    safer to skip than to guess).
    """
    doc = Document(BytesIO(original_bytes))
    applied = 0

    def _walk_paragraphs():
        for p in doc.paragraphs:
            yield p
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        yield p

    for edit in edits:
        find = edit.get("find", "").strip()
        replace = edit.get("replace", "").strip()
        if not find or not replace:
            continue
        for paragraph in _walk_paragraphs():
            if _replace_in_paragraph(paragraph, find, replace):
                applied += 1
                break  # only replace the first match for this edit

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read(), applied
