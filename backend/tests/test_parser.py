"""Tests for parser.py — document extraction and truncation."""

import io
import os

import pytest
from fastapi import UploadFile

from parser import extract_text, truncate

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _make_upload(filepath: str, filename: str) -> UploadFile:
    """Create an UploadFile from a fixture file path."""
    f = open(filepath, "rb")
    return UploadFile(filename=filename, file=f)


def _make_upload_from_bytes(content: bytes, filename: str) -> UploadFile:
    """Create an UploadFile from raw bytes."""
    return UploadFile(filename=filename, file=io.BytesIO(content))


# --- PDF extraction ---

class TestPDFExtraction:
    def test_pdf_extracts_text(self):
        upload = _make_upload(os.path.join(FIXTURES, "sample.pdf"), "sample.pdf")
        text = extract_text(upload)
        assert "sample PDF document" in text
        upload.file.close()

    def test_empty_pdf_raises(self):
        upload = _make_upload(os.path.join(FIXTURES, "empty.pdf"), "empty.pdf")
        with pytest.raises(ValueError, match="empty"):
            extract_text(upload)
        upload.file.close()


# --- DOCX extraction ---

class TestDOCXExtraction:
    def test_docx_extracts_text(self):
        upload = _make_upload(os.path.join(FIXTURES, "sample.docx"), "sample.docx")
        text = extract_text(upload)
        assert "sample DOCX document" in text
        upload.file.close()


# --- TXT extraction ---

class TestTXTExtraction:
    def test_txt_extracts_text(self):
        upload = _make_upload(os.path.join(FIXTURES, "sample.txt"), "sample.txt")
        text = extract_text(upload)
        assert "sample TXT document" in text
        upload.file.close()

    def test_empty_txt_raises(self):
        upload = _make_upload(os.path.join(FIXTURES, "empty.txt"), "empty.txt")
        with pytest.raises(ValueError, match="empty"):
            extract_text(upload)
        upload.file.close()


# --- Unsupported file type ---

class TestUnsupportedType:
    def test_unsupported_extension_raises(self):
        upload = _make_upload_from_bytes(b"data", "image.png")
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text(upload)

    def test_no_extension_raises(self):
        upload = _make_upload_from_bytes(b"data", "noext")
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text(upload)


# --- Truncation ---

class TestTruncation:
    def test_short_text_unchanged(self):
        text = "word " * 100
        result = truncate(text, max_words=8000)
        assert result == text

    def test_exact_boundary_unchanged(self):
        text = " ".join(f"w{i}" for i in range(8000))
        result = truncate(text, max_words=8000)
        assert result == text

    def test_over_boundary_truncated(self):
        words = [f"w{i}" for i in range(8500)]
        text = " ".join(words)
        result = truncate(text, max_words=8000)
        result_words = result.split("\n\n")[0].split()
        assert len(result_words) == 8000
        assert "[Document truncated at 8,000 words]" in result

    def test_truncation_notice_appended(self):
        text = " ".join(["hello"] * 10000)
        result = truncate(text, max_words=5)
        assert result.endswith("[Document truncated at 8,000 words]")
        # Only 5 words before the notice
        body = result.split("\n\n")[0]
        assert len(body.split()) == 5
