"""Extracts plain text from uploaded documents.

Dispatches on MIME type. Adding support for another file type means: add a
branch here, and add its MIME type to core.config's upload validation.
"""

import io

from docx import Document as DocxDocument
from pypdf import PdfReader

from src.core.exceptions import UnsupportedFileTypeError

PDF_CONTENT_TYPE = "application/pdf"
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

SUPPORTED_CONTENT_TYPES = {PDF_CONTENT_TYPE, DOCX_CONTENT_TYPE}


def extract_text(file_bytes: bytes, content_type: str) -> str:
    if content_type == PDF_CONTENT_TYPE:
        return _extract_pdf_text(file_bytes)
    if content_type == DOCX_CONTENT_TYPE:
        return _extract_docx_text(file_bytes)
    raise UnsupportedFileTypeError(
        f"Unsupported file type: '{content_type}'. Upload a PDF or DOCX file."
    )


def _extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    # extract_text() returns None for pages pypdf can't parse (e.g. a
    # scanned/image-only page with no text layer) rather than raising —
    # fall back to "" so one bad page doesn't lose the rest of the document.
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def _extract_docx_text(file_bytes: bytes) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n\n".join(paragraphs)
