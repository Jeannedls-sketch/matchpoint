"""
Extracts raw text from uploaded candidate documents (CV, cover letter,
transcripts, recommendation letters, certifications).

Supports PDF and DOCX. Returns plain text ready to feed to Claude.
"""

from io import BytesIO
from pypdf import PdfReader
from docx import Document


def extract_text_from_file(uploaded_file) -> str:
    """
    Takes a Streamlit UploadedFile object and returns extracted plain text.
    Supports .pdf and .docx. Raises ValueError on unsupported types.
    """
    name = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)  # reset pointer in case it's read again elsewhere

    if name.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    elif name.endswith(".docx"):
        return _extract_docx(file_bytes)
    elif name.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type: {uploaded_file.name}")


def _extract_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _extract_docx(file_bytes: bytes) -> str:
    doc = Document(BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # also pull table content, some CVs/transcripts use tables for layout
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))
    return "\n".join(paragraphs)


def extract_all(uploaded_files: dict) -> dict:
    """
    uploaded_files: dict like {"cv": UploadedFile, "cover_letter": UploadedFile, ...}
    Returns: dict of {doc_type: extracted_text}, skipping any that are None.
    """
    results = {}
    for doc_type, file in uploaded_files.items():
        if file is not None:
            try:
                results[doc_type] = extract_text_from_file(file)
            except Exception as e:
                results[doc_type] = f"[Error extracting {doc_type}: {e}]"
    return results
