"""In-memory session store for chat context."""

import uuid

_store: dict[str, dict] = {}


def create_session(document_text: str) -> str:
    """Create a new session with the given document text. Returns session ID."""
    session_id = str(uuid.uuid4())
    _store[session_id] = {
        "document_text": document_text,
        "chat_history": [],
    }
    return session_id


def get_session(session_id: str) -> dict:
    """Return the session dict. Raises KeyError if not found."""
    if session_id not in _store:
        raise KeyError(f"Session not found: {session_id}")
    return _store[session_id]


def append_message(session_id: str, role: str, content: str) -> None:
    """Append a message to the session's chat history."""
    session = get_session(session_id)
    session["chat_history"].append({"role": role, "content": content})
