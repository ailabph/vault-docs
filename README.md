# vault-docs

**Air-Gapped Document Analyzer**

Upload a document. Get a summary, key points, and a chat interface to ask questions about it. No data ever leaves your machine.

> "This document never leaves your system." — 100% locally hosted. Zero cloud dependencies.

---

## What It Does

1. **Upload** — Drag and drop a PDF, TXT, or DOCX
2. **Analyze** — A local LLM extracts text, generates a 3–5 sentence summary, and pulls key points
3. **Ask** — Chat with the document using a built-in Q&A interface
4. **Trust** — Every step runs on your hardware. No external API calls. No telemetry.

This is the first release in aiLab.ph's **Weekly Proof of Product** series — open-source tools that demonstrate sovereign AI is real, production-ready, and available today.

---

## Stack

| Layer | Technology |
|---|---|
| LLM Inference | [Ollama](https://ollama.com) with Qwen3 32B |
| Document Parsing | Python (PyMuPDF, python-docx) |
| Backend | FastAPI |
| Frontend | Vanilla JS — dark theme |
| Deployment | Docker Compose |

Hardware tested on: 4x NVIDIA RTX A5000 (96GB total VRAM)

---

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- GPU with sufficient VRAM (16GB+ recommended; 96GB for Qwen3 32B)

### Run

```bash
git clone https://github.com/ailabph/vault-docs.git
cd vault-docs
docker compose up
```

Open `http://localhost:3000` in your browser.

That's it. No API keys. No accounts. No cloud.

---

## How It Works

```
User uploads document
        │
        ▼
 Text extraction (local)
  PDF → PyMuPDF
  DOCX → python-docx
  TXT → direct read
        │
        ▼
  Ollama (Qwen3 32B)
  ┌─────────────────┐
  │  Summary        │
  │  Key Points     │
  │  Q&A context    │
  └─────────────────┘
        │
        ▼
   Web Interface
   (stays on your machine)
```

No data crosses a network boundary. The inference endpoint is `localhost`. The document never touches an external server.

---

## Configuration

Edit `docker-compose.yml` to change the model or port:

```yaml
environment:
  - OLLAMA_MODEL=qwen3:32b       # swap for any model you have pulled
  - APP_PORT=3000
```

To use a different model:

```bash
ollama pull mistral
# then set OLLAMA_MODEL=mistral in docker-compose.yml
```

---

## Performance

Tested on a 10-page PDF with Qwen3 32B:

| Operation | Time |
|---|---|
| Text extraction | < 1s |
| Summary + key points | ~15–25s |
| Follow-up Q&A | ~5–10s per response |

Results under 30 seconds. Hardware will vary.

---

## Project Structure

```
vault-docs/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── main.py          # FastAPI app
│   ├── parser.py        # Document text extraction
│   └── llm.py           # Ollama inference client
├── frontend/
│   ├── Dockerfile
│   ├── index.html
│   ├── style.css
│   └── app.js
└── README.md
```

---

## Why This Exists

Most AI tools phone home. Every document you analyze with a cloud API leaves your network — potentially landing in a training dataset, a vendor's log, or a compliance gap.

vault-docs is proof that the trade-off is false. You don't have to choose between capable AI and data sovereignty. Modern open-weight models running on commodity hardware are good enough — and this tool demonstrates that with something you can deploy yourself in one command.

This is aiLab.ph's first weekly open-source release. We build software for high-stakes environments where reliability and security aren't optional. This is what that looks like in practice.

---

## License

Apache 2.0 — see [LICENSE](./LICENSE)

---

## Built by

[aiLab.ph](https://ailab.ph) — building software where bugs have dollar signs attached.

`Powered by Qwen3 32B • No external APIs`
