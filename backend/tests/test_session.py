"""Tests for session.py — in-memory session store."""

import uuid

import pytest

from session import _store, append_message, create_session, get_session


@pytest.fixture(autouse=True)
def clear_store():
    """Clear the session store before each test."""
    _store.clear()
    yield
    _store.clear()


class TestCreateSession:
    def test_returns_valid_uuid(self):
        sid = create_session("doc text")
        uuid.UUID(sid)  # raises if invalid

    def test_stores_document_text(self):
        sid = create_session("hello world")
        assert _store[sid]["document_text"] == "hello world"

    def test_initializes_empty_history(self):
        sid = create_session("text")
        assert _store[sid]["chat_history"] == []


class TestGetSession:
    def test_returns_correct_session(self):
        sid = create_session("my doc")
        session = get_session(sid)
        assert session["document_text"] == "my doc"
        assert session["chat_history"] == []

    def test_unknown_id_raises_key_error(self):
        with pytest.raises(KeyError, match="Session not found"):
            get_session("nonexistent-id")


class TestAppendMessage:
    def test_appends_user_message(self):
        sid = create_session("doc")
        append_message(sid, "user", "What is this?")
        history = get_session(sid)["chat_history"]
        assert len(history) == 1
        assert history[0] == {"role": "user", "content": "What is this?"}

    def test_appends_multiple_messages(self):
        sid = create_session("doc")
        append_message(sid, "user", "Q1")
        append_message(sid, "assistant", "A1")
        append_message(sid, "user", "Q2")
        history = get_session(sid)["chat_history"]
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"

    def test_append_to_unknown_session_raises(self):
        with pytest.raises(KeyError):
            append_message("bad-id", "user", "hello")
