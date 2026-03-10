# Requirements

## Functional Requirements

### Document Ingestion
- Accept PDF, TXT, and DOCX file formats
- Extract raw text content from uploaded documents
- Reject files exceeding the configured size limit
- Reject unsupported file types before processing

### AI Analysis
- Generate a 3–5 sentence summary of the document
- Extract key points as a structured bullet list
- Provide a chat interface where users can ask questions about the document
- All inference must use the locally running Ollama instance

### Chat
- Maintain document context throughout the session
- Support multi-turn conversation within a single document session
- Chat history visible within the active session

### Interface
- Web-based UI accessible via browser
- Drag-and-drop and click-to-upload file input
- Processing indicator during analysis
- Display sovereignty messaging throughout the experience (see UI Messaging below)

### UI Messaging (Required Verbatim)
The following phrases must appear in the interface:
- "Air-Gapped Document Analyzer"
- "Your document never leaves our private infrastructure"
- "100% privately hosted — no cloud, no third parties"
- "Zero cloud dependencies"
- "Powered by [model name] • No external APIs"

---

## Non-Functional Requirements

### Performance
- Summary + key points delivered in under 30 seconds for a 10-page document on target hardware (4x RTX A5000)
- Chat responses under 10 seconds per turn

### Data Sovereignty
- Zero outbound network requests during document processing
- No document content persisted to disk beyond the active request lifecycle
- Ollama inference endpoint reached via SSH tunnel only (`host.docker.internal:11434`)
- Document text truncated to 8,000 words before prompt submission (v1 context window policy)

### Deployment
- Single command to start the VPS stack: `docker compose up`
- Model pull is a **manual one-time bootstrap step** on the GPU server: `ollama pull qwen3:32b`
- The GPU server and SSH tunnel must be running before `docker compose up` is executed

### Compatibility
- **VPS** — Linux host with Docker and Docker Compose (no GPU required)
- **GPU server** — Linux host with NVIDIA GPU, `nvidia-container-toolkit`, and Ollama installed
- Browser support: latest Chrome, Firefox, Edge

---

## Technical Stack (Decided)

| Concern | Decision |
|---|---|
| LLM Inference | Ollama |
| Default Model | Qwen3 32B |
| Backend | FastAPI (Python) |
| PDF Parsing | PyMuPDF (`fitz`) |
| DOCX Parsing | python-docx |
| Frontend | Vanilla JS (no framework, no build step) |
| Deployment | Docker Compose |
| License | Apache 2.0 |

---

## Out of Scope (This Release)

- User authentication or authorization
- Multi-user support
- Document storage or history
- Support for additional file types (images, spreadsheets, etc.)
- Batch document processing
- Export of analysis results
- Mobile-optimized UI
- Any cloud deployment option
