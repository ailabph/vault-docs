"""Tests for API endpoints — POST /api/analyze and POST /api/chat."""

import io
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from session import _store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear session store between tests."""
    _store.clear()
    yield
    _store.clear()


# ---------------------------------------------------------------------------
# POST /api/analyze
# ---------------------------------------------------------------------------


class TestAnalyzeEndpoint:
    def _upload(self, content: bytes, filename: str):
        return client.post(
            "/api/analyze",
            files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
        )

    @patch("main.llm.analyze", new_callable=AsyncMock)
    @patch("main.parser.extract_text")
    def test_success_returns_correct_shape(self, mock_extract, mock_analyze):
        mock_extract.return_value = "Extracted document text."
        mock_analyze.return_value = {
            "summary": "A brief summary.",
            "key_points": ["Point 1", "Point 2"],
        }

        resp = self._upload(b"fake pdf bytes", "test.pdf")

        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["summary"] == "A brief summary."
        assert data["key_points"] == ["Point 1", "Point 2"]

    @patch("main.llm.analyze", new_callable=AsyncMock)
    @patch("main.parser.extract_text")
    def test_session_created_after_analyze(self, mock_extract, mock_analyze):
        mock_extract.return_value = "doc text"
        mock_analyze.return_value = {"summary": "s", "key_points": []}

        resp = self._upload(b"data", "test.txt")
        sid = resp.json()["session_id"]
        assert sid in _store

    def test_bad_file_type_returns_400(self):
        with patch("main.parser.extract_text", side_effect=ValueError("Unsupported file type: '.png'")):
            resp = self._upload(b"image data", "photo.png")

        assert resp.status_code == 400
        assert "error" in resp.json()
        assert "stack" not in resp.text.lower()

    def test_empty_file_returns_400(self):
        with patch("main.parser.extract_text", side_effect=ValueError("Document is empty")):
            resp = self._upload(b"", "empty.txt")

        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_oversized_file_returns_413(self):
        # Create content larger than MAX_UPLOAD_SIZE_MB (default 50MB)
        with patch("main.MAX_UPLOAD_SIZE_MB", 0):  # 0 MB limit → everything is oversized
            resp = self._upload(b"some data", "big.pdf")

        assert resp.status_code == 413
        assert "error" in resp.json()

    @patch("main.parser.extract_text", return_value="doc text")
    @patch("main.llm.analyze", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused"))
    def test_ollama_down_returns_503(self, mock_analyze, mock_extract):
        resp = self._upload(b"data", "test.txt")

        assert resp.status_code == 503
        assert "error" in resp.json()
        assert "unavailable" in resp.json()["error"].lower()

    @patch("main.parser.extract_text", return_value="doc text")
    @patch("main.llm.analyze", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout"))
    def test_ollama_timeout_returns_503(self, mock_analyze, mock_extract):
        resp = self._upload(b"data", "test.txt")

        assert resp.status_code == 503

    def test_no_stack_trace_in_400(self):
        with patch("main.parser.extract_text", side_effect=ValueError("bad file")):
            resp = self._upload(b"data", "bad.xyz")

        body = resp.text
        assert "Traceback" not in body
        assert "File \"" not in body


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    def _create_session_with_doc(self, doc_text: str = "Document content.") -> str:
        """Helper: manually create a session and return its ID."""
        from session import create_session
        return create_session(doc_text)

    @patch("main.llm.chat", new_callable=AsyncMock, return_value="The answer is 42.")
    def test_success_returns_answer(self, mock_chat):
        sid = self._create_session_with_doc()

        resp = client.post("/api/chat", json={"session_id": sid, "question": "What is the answer?"})

        assert resp.status_code == 200
        assert resp.json()["answer"] == "The answer is 42."

    def test_unknown_session_returns_404(self):
        resp = client.post("/api/chat", json={"session_id": "nonexistent", "question": "Hi"})

        assert resp.status_code == 404
        assert "error" in resp.json()

    @patch("main.llm.chat", new_callable=AsyncMock, return_value="Response 1")
    def test_appends_both_turns_to_history(self, mock_chat):
        sid = self._create_session_with_doc()

        client.post("/api/chat", json={"session_id": sid, "question": "Q1"})

        history = _store[sid]["chat_history"]
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Q1"}
        assert history[1] == {"role": "assistant", "content": "Response 1"}

    @patch("main.llm.chat", new_callable=AsyncMock)
    def test_multi_turn_grows_history(self, mock_chat):
        mock_chat.side_effect = ["A1", "A2"]
        sid = self._create_session_with_doc()

        client.post("/api/chat", json={"session_id": sid, "question": "Q1"})
        client.post("/api/chat", json={"session_id": sid, "question": "Q2"})

        history = _store[sid]["chat_history"]
        assert len(history) == 4  # Q1, A1, Q2, A2

    @patch("main.llm.chat", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused"))
    def test_ollama_down_returns_503(self, mock_chat):
        sid = self._create_session_with_doc()

        resp = client.post("/api/chat", json={"session_id": sid, "question": "Hi"})

        assert resp.status_code == 503
        assert "error" in resp.json()

    @patch("main.llm.chat", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout"))
    def test_ollama_timeout_returns_503(self, mock_chat):
        sid = self._create_session_with_doc()

        resp = client.post("/api/chat", json={"session_id": sid, "question": "Hi"})

        assert resp.status_code == 503

    def test_no_stack_trace_in_404(self):
        resp = client.post("/api/chat", json={"session_id": "bad", "question": "Hi"})

        body = resp.text
        assert "Traceback" not in body
        assert "File \"" not in body
