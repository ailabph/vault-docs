# Streaming Chat Response

## Problem

qwen3.5:35b is a thinking model — it generates internal reasoning tokens (`<think>...</think>`) before producing the visible answer. On large documents with multi-turn history, this can take 30-120+ seconds. During this time the user sees no feedback, making the UI appear frozen.

## Solution

Stream tokens from Ollama to the browser in real-time via Server-Sent Events (SSE). Show thinking tokens in a collapsible dimmed block, then render the actual answer as it arrives.

## User Experience

```
User sends question
     │
     ▼
┌─────────────────────────────────────────┐
│  Thinking...                        [▼] │  ← dimmed, collapsible
│  Let me analyze the transactions...     │
│  Looking at Lazada purchases...         │
│  Calculating total from entries...      │
└─────────────────────────────────────────┘
│
│  (thinking block collapses when answer starts)
│
┌─────────────────────────────────────────┐
│  The total online shopping spend is     │  ← normal assistant bubble
│  PHP 45,230.00 across 12 transactions.  │    streams token-by-token
└─────────────────────────────────────────┘
```

## Scope

| Endpoint | Streaming | Reason |
|---|---|---|
| `POST /api/chat` | Yes | User waits in the results state, needs feedback |
| `POST /api/analyze` | No | User sees the spinner in the processing state — feedback is already visible |

## Architecture

### Current flow (blocking)

```
Browser ──POST /api/chat──► FastAPI ──POST stream:false──► Ollama
                                     (waits for full response)
Browser ◄──JSON {answer}──── FastAPI ◄──full JSON───────── Ollama
```

### Proposed flow (streaming)

```
Browser ──POST /api/chat──► FastAPI ──POST stream:true──► Ollama
                                                          │
Browser ◄──SSE: token──────── FastAPI ◄──NDJSON chunk───── Ollama
Browser ◄──SSE: token──────── FastAPI ◄──NDJSON chunk───── Ollama
Browser ◄──SSE: token──────── FastAPI ◄──NDJSON chunk───── Ollama
  ...                                    ...
Browser ◄──SSE: [DONE]─────── FastAPI ◄──done:true──────── Ollama
```

## Backend Changes

### `backend/llm.py`

Add `chat_stream()` — an async generator that yields tokens from Ollama's streaming response.

```python
async def chat_stream(context: str, history: list[dict], question: str):
    """Stream chat tokens from Ollama. Yields (token, done) tuples."""
    messages = _build_chat_messages(context, history, question)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_HOST}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                done = chunk.get("done", False)
                yield token, done
```

The existing non-streaming `chat()` stays for backward compatibility and is still used by tests.

### `backend/main.py`

Change `POST /api/chat` to return `StreamingResponse` with SSE format.

```python
from fastapi.responses import StreamingResponse

@app.post("/api/chat")
async def chat(req: ChatRequest):
    # session lookup (unchanged)
    # ...

    async def event_stream():
        full_answer = []
        try:
            async for token, done in llm.chat_stream(
                context=sess["document_text"],
                history=sess["chat_history"],
                question=req.question,
            ):
                full_answer.append(token)
                yield f"data: {json.dumps({'token': token, 'done': done})}\n\n"
        except (httpx.TimeoutException, httpx.ConnectError, ...):
            yield f"data: {json.dumps({'error': 'Service unavailable'})}\n\n"
            return

        # persist turns after stream completes
        answer_text = "".join(full_answer)
        session.append_message(req.session_id, "user", req.question)
        session.append_message(req.session_id, "assistant", answer_text)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### SSE message format

Each SSE event is a JSON payload:

```
data: {"token": "<think>\n", "done": false}

data: {"token": "Let me", "done": false}

data: {"token": " analyze", "done": false}

...

data: {"token": "", "done": true}
```

Error case:
```
data: {"error": "Service unavailable"}
```

## Frontend Changes

### `frontend/app.js`

Replace the `fetch` + `response.json()` in `sendChatMessage()` with a streaming reader.

```
sendChatMessage()
  ├── fetch('/api/chat', ...)
  ├── response.body.getReader()
  ├── Read loop:
  │     ├── Parse SSE "data: {...}" lines
  │     ├── If token is inside <think>...</think>:
  │     │     └── Append to thinking block (dimmed, collapsible)
  │     ├── If token is outside <think>:
  │     │     └── Append to answer bubble (normal style)
  │     └── If done or error: break
  ├── Collapse thinking block
  └── Re-enable input
```

**Thinking detection:** Track state with a simple flag:
- When `<think>` is encountered in the accumulated text → switch to thinking mode
- When `</think>` is encountered → switch back to answer mode
- Tokens in thinking mode go to the thinking block
- Tokens in answer mode go to the answer bubble

### `frontend/style.css`

New styles:

```css
.thinking-block {
    align-self: flex-start;
    max-width: 80%;
    padding: 0.75rem 1rem;
    border-radius: var(--radius);
    background: var(--bg-surface);
    border: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.8rem;
    font-style: italic;
    line-height: 1.5;
    white-space: pre-wrap;
    max-height: 120px;
    overflow-y: auto;
    transition: max-height 0.3s ease, opacity 0.3s ease;
}

.thinking-block.collapsed {
    max-height: 2rem;
    overflow: hidden;
    cursor: pointer;
    opacity: 0.6;
}

.thinking-label {
    color: var(--text-muted);
    font-size: 0.75rem;
    margin-bottom: 0.25rem;
}
```

## Nginx

No changes needed. `proxy_read_timeout 300s` already covers the streaming connection. SSE works over standard HTTP — no WebSocket upgrade required.

## Test Impact

Existing `test_api.py` tests mock `llm.chat()` (non-streaming). Two options:

1. **Keep non-streaming `chat()` in llm.py** — existing tests stay unchanged. Add new tests for `chat_stream()` and the SSE endpoint separately.
2. The `/api/chat` endpoint changes to return SSE instead of JSON — update `test_api.py` to read SSE responses.

Recommended: option 1 — keep `chat()` for tests, add `chat_stream()` for the endpoint.

## Constraints

- No new dependencies — `httpx` already supports streaming, `FastAPI` already has `StreamingResponse`, SSE is plain text over HTTP.
- `/api/analyze` stays non-streaming.
- Session history still stores the full answer text (assembled from streamed tokens after completion).
- Privacy model unchanged — all tokens flow through the same private path (browser → VPS → tunnel → GPU server).
