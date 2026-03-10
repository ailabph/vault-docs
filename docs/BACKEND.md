# Backend

## Overview

FastAPI application responsible for document parsing, prompt construction, and Ollama communication. Stateless per request except for in-memory session context used for Q&A chat history.

## Stack

| Concern | Library |
|---|---|
| Framework | FastAPI |
| ASGI Server | Uvicorn |
| PDF Parsing | PyMuPDF (`fitz`) |
| DOCX Parsing | python-docx |
| HTTP Client (Ollama) | httpx (async) |
| Runtime | Python 3.11+ |

## Module Structure

```
backend/
├── main.py          API routes and app entrypoint
├── parser.py        Document text extraction
├── llm.py           Ollama client — prompt building and inference calls
├── session.py       In-memory session store for chat context
├── config.py        Environment variable loading (OLLAMA_MODEL, OLLAMA_HOST, etc.)
├── requirements.txt
└── Dockerfile
```

## API Endpoints

### `POST /api/analyze`
Accepts a multipart file upload. Extracts text, sends to Ollama for summary and key points, returns structured response.

**Request:** `multipart/form-data` — field `file`

**Response:**
```json
{
  "session_id": "uuid",
  "summary": "...",
  "key_points": ["...", "...", "..."]
}
```

**Errors:**
- `400` — unsupported file type or text extraction failure
- `413` — file exceeds size limit
- `503` — Ollama unavailable

---

### `POST /api/chat`
Accepts a question and session ID. Retrieves document context and chat history, sends to Ollama, returns answer.

**Request:**
```json
{
  "session_id": "uuid",
  "question": "What is the main argument?"
}
```

**Response:**
```json
{
  "answer": "..."
}
```

**Errors:**
- `404` — session not found
- `503` — Ollama unavailable

---

### `GET /api/health`
Returns 200 if the backend is up and Ollama is reachable.

## Text Truncation Policy

Before any text is sent to Ollama, it is truncated to a maximum of **8,000 words**.

This prevents context window overflow on large documents. Truncation happens in `parser.py` after extraction, before the text is passed to `llm.py`.

```python
def truncate(text: str, max_words: int = 8000) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "\n\n[Document truncated at 8,000 words]"
```

The truncation notice is appended so the model is aware the document is incomplete. Proper chunking and map-reduce summarization is a future improvement.

---

## parser.py

Dispatches to the correct parser based on file extension. Returns a plain text string.

```python
def extract_text(file: UploadFile) -> str
    # .pdf  → fitz.open()
    # .docx → Document(file).paragraphs
    # .txt  → file.read().decode()
```

Raises `ValueError` if the file type is unsupported or extraction yields empty text.

## llm.py

Thin async wrapper around the Ollama `/api/chat` endpoint.

- Builds a two-prompt structure: system instructions + user content
- For `/analyze`: single-turn prompt requesting summary and key points in a structured format
- For `/chat`: multi-turn messages array including document context and full chat history
- Streams or awaits full response depending on use case (TBD — full response preferred for simplicity)

```python
async def analyze(text: str) -> dict  # { summary, key_points }
async def chat(context: str, history: list, question: str) -> str
```

## session.py

Simple in-memory dict keyed by `session_id` (UUID). Stores:

```python
{
  "session_id": {
    "document_text": str,
    "chat_history": [ { "role": "user"|"assistant", "content": str } ]
  }
}
```

No persistence. Sessions are lost on container restart. No TTL in v1 — acceptable for a single-user demo tool.

## Prompts

### Analysis Prompt
```
System: You are a document analysis assistant. Be concise and accurate.
User:   Analyze the following document.
        Return exactly:
        SUMMARY: <3-5 sentence summary>
        KEY POINTS:
        - <point>
        - <point>
        ...

        Document:
        {extracted_text}
```

### Chat Prompt
```
System: You are answering questions about a document provided by the user.
        Only use information from the document. If the answer is not in the
        document, say so.
User:   [Document text on first turn, then questions]
```

## Error Handling

- Parser errors return `400` with a descriptive message — never expose stack traces to the client
- Ollama timeouts return `503` — the frontend should surface a retry option
- Session not found returns `404`

## Configuration (config.py)

All values loaded from environment variables with sensible defaults:

```python
OLLAMA_HOST       = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "qwen3:32b")
MAX_UPLOAD_MB     = int(os.getenv("MAX_UPLOAD_SIZE_MB", 50))
MAX_WORDS_PROMPT  = int(os.getenv("MAX_WORDS_PROMPT", 8000))
```

> **Note:** `host.docker.internal` resolves to the Docker host via `extra_hosts: host-gateway` in `docker-compose.yml`. This routes backend → SSH tunnel → GPU server Ollama without needing `network_mode: host`.
