# Application Flow Chart

## End-to-End User Flow

```
┌─────────────────────────────────────────────────────────┐
│                     USER BROWSER                        │
│                  localhost:3000                         │
└──────────────────────────┬──────────────────────────────┘
                           │
                    1. Upload file
                    (drag/drop or click)
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   FRONTEND (Nginx)                      │
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
│                  BACKEND (FastAPI)                      │
│                  backend:8000                           │
│                                                         │
│  parser.py                                              │
│  ┌──────────────────────────────────────┐               │
│  │  if .pdf  → PyMuPDF (fitz)           │               │
│  │  if .docx → python-docx              │               │
│  │  if .txt  → direct read              │               │
│  └──────────────┬───────────────────────┘               │
│                 │                                       │
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
         3. POST /api/chat
         { model, messages }
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                  OLLAMA (Inference)                     │
│                  ollama:11434                           │
│                                                         │
│  Model: Qwen3 32B (or OLLAMA_MODEL env var)             │
│  GPU: 4x RTX A5000 via nvidia-container-toolkit         │
│                                                         │
│  Returns: streaming or full text response               │
└──────────────────────────┬──────────────────────────────┘
                           │
                  4. Response JSON
                  { summary, key_points }
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI)                      │
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
Backend (FastAPI)
  - Retrieves document context for session
  - Builds messages array:
      [ system, document_context, chat_history..., user_question ]
  - Sends to Ollama
        │
        ▼
Ollama
  - Generates answer grounded in document context
  - Returns response text
        │
        ▼
Backend
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

Ollama → Timeout or unavailable
        │
        └── Backend returns 503 { error: "Inference service unavailable" }

All errors → Frontend displays inline error message, resets to upload state
```

---

## Data Boundaries

```
┌──────────────────────────────────────┐
│           HOST MACHINE               │
│                                      │
│  ┌──────────┐  ┌────────┐  ┌──────┐  │
│  │ frontend │  │backend │  │ollama│  │
│  └──────────┘  └────────┘  └──────┘  │
│                                      │
│  Docker internal network only        │
│  No traffic exits this boundary      │
└──────────────────────────────────────┘

Internet ✗ — no outbound connections at any layer
```
