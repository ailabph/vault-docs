# Application Flow Chart

## End-to-End User Flow

```
┌─────────────────────────────────────────────────────────┐
│                     USER BROWSER                        │
│                   https://vps:3000                      │
└──────────────────────────┬──────────────────────────────┘
                           │
                    1. Upload file
                    (drag/drop or click)
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                VPS — FRONTEND (Nginx)                   │
│                                                         │
│  - Validates file type (PDF / TXT / DOCX)               │
│  - Validates file size                                  │
│  - Shows upload progress indicator                      │
└──────────────────────────┬──────────────────────────────┘
                           │
                  2. POST /api/analyze
                  multipart/form-data
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                VPS — BACKEND (FastAPI)                  │
│                   backend:8000                          │
│                                                         │
│  parser.py                                              │
│  ┌──────────────────────────────────────┐               │
│  │  if .pdf  → PyMuPDF (fitz)           │               │
│  │  if .docx → python-docx              │               │
│  │  if .txt  → direct read              │               │
│  └──────────────┬───────────────────────┘               │
│                 │  extracted plain text                 │
│                 ▼                                       │
│  llm.py                                                 │
│  ┌──────────────────────────────────────┐               │
│  │  Build prompt:                       │               │
│  │    - System: "You are analyzing..."  │               │
│  │    - User: [extracted text]          │               │
│  │    - Task: summarize + key points    │               │
│  └──────────────┬───────────────────────┘               │
└─────────────────┼───────────────────────────────────────┘
                  │
         3. POST http://localhost:11434/api/chat
            (via SSH tunnel → GPU server)
                  │
  ════════════════╪════════════════════════════════════════
  SSH TUNNEL      │         VPS localhost:11434
                  │              ↕ tunneled
                  │         GPU Server localhost:11434
  ════════════════╪════════════════════════════════════════
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│             GPU SERVER — OLLAMA                         │
│                localhost:11434                          │
│                                                         │
│  Model: Qwen3.5 35B                                       │
│  Hardware: 4x RTX A5000 (96GB VRAM)                     │
│                                                         │
│  Returns: inference response                            │
└──────────────────────────┬──────────────────────────────┘
                           │
                  4. Response (via tunnel)
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                VPS — BACKEND (FastAPI)                  │
│                                                         │
│  - Parses Ollama response                               │
│  - Structures output: { summary, key_points }           │
│  - Stores document text in session context for Q&A      │
└──────────────────────────┬──────────────────────────────┘
                           │
                  5. JSON response
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   FRONTEND (Browser)                    │
│                                                         │
│  - Renders summary paragraph                            │
│  - Renders key points as bullet list                    │
│  - Activates chat input                                 │
└─────────────────────────────────────────────────────────┘
```

---

## Chat / Q&A Flow (Post-Analysis)

```
User types question
        │
        ▼
Frontend
  POST /api/chat
  { session_id, question }
        │
        ▼
Backend (FastAPI) — VPS
  - Retrieves document context for session
  - Builds messages array:
      [ system, document_context, chat_history..., user_question ]
  - Sends to localhost:11434 (SSH tunnel)
        │
    [SSH tunnel]
        │
        ▼
Ollama — GPU Server
  - Generates answer grounded in document context
  - Returns response text
        │
    [SSH tunnel]
        │
        ▼
Backend — VPS
  - Appends exchange to session chat history
  - Returns { answer }
        │
        ▼
Frontend
  - Appends to chat UI
  - User can ask follow-up
```

---

## Error Flow

```
Upload → Invalid type or size
        │
        └── Frontend rejects immediately (no server call)

Upload → Server-side parse failure
        │
        └── Backend returns 400 { error: "Could not extract text from document" }

SSH tunnel → Down or disconnected
        │
        └── Backend returns 503 { error: "Inference service unavailable" }
            (tunnel must be re-established manually or via systemd restart)

Ollama → Timeout or model not loaded
        │
        └── Backend returns 503 { error: "Inference service unavailable" }

All errors → Frontend displays inline error message, resets to upload state
```

---

## Data Boundaries

```
┌─────────────────────────────────┐     ┌──────────────────────────────┐
│             VPS                 │     │         GPU SERVER            │
│                                 │     │                              │
│  ┌──────────┐  ┌─────────────┐  │     │  ┌────────────────────────┐  │
│  │ frontend │  │   backend   │  │     │  │  Ollama (Qwen3.5 35B)    │  │
│  │ (Nginx)  │  │  (FastAPI)  │  │     │  │  localhost:11434       │  │
│  └──────────┘  └──────┬──────┘  │     │  └────────────────────────┘  │
│                       │         │     │              ▲               │
│               localhost:11434   │     │              │               │
│                       │  SSH tunnel (encrypted)      │               │
│                       └─────────────────────────────►│               │
│                                 │     │                              │
└─────────────────────────────────┘     └──────────────────────────────┘

Document text travels:  Browser → VPS (HTTPS) → GPU Server (SSH tunnel)
No data touches any third-party server at any point.
```
