"""Document text extraction and truncation."""

import io
import os

import fitz  # PyMuPDF
from docx import Document
from fastapi import UploadFile

from config import MAX_WORDS_PROMPT

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def extract_text(file: UploadFile) -> str:
    """Extract plain text from an uploaded PDF, DOCX, or TXT file.

    Raises ValueError for unsupported file types or empty documents.
    """
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: '{ext}'. Accepted: .pdf, .docx, .txt")

    content = file.file.read()

    if ext == ".pdf":
        text = _extract_pdf(content)
    elif ext == ".docx":
        text = _extract_docx(content)
    else:  # .txt
        text = _extract_txt(content)

    text = text.strip()
    if not text:
        raise ValueError("Document is empty — no text could be extracted.")

    return text


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    doc = fitz.open(stream=content, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def _extract_docx(content: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_txt(content: bytes) -> str:
    """Decode TXT bytes to string."""
    return content.decode("utf-8")


def truncate(text: str, max_words: int = MAX_WORDS_PROMPT) -> str:
    """Truncate text to max_words. Appends notice when truncation occurs."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "\n\n[Document truncated at 8,000 words]"
