# vault-docs

**Air-Gapped Document Analyzer**

Upload a document. Get a summary, key points, and a chat interface to ask questions about it. No data ever reaches a cloud provider or third-party service.

> "Your document never leaves our private infrastructure." — No cloud. No third parties. Zero external API calls.

---

## What It Does

1. **Upload** — Drag and drop a PDF, TXT, or DOCX
2. **Analyze** — A privately hosted LLM (Qwen3.5 9B) extracts text, generates a 3–5 sentence summary, and pulls key points
3. **Ask** — Chat with the document using a built-in Q&A interface
4. **Monitor** — Real-time GPU status bar shows connection state, loaded models with VRAM usage, and hardware info
5. **Trust** — Processed entirely on private infrastructure. No cloud APIs. No telemetry.

This is the first release in aiLab.ph's **Weekly Proof of Product** series — open-source tools that demonstrate sovereign AI is real, production-ready, and available today.

---

## Stack

| Layer | Technology |
|---|---|
| LLM Inference | [Ollama](https://ollama.com) with Qwen3.5 9B |
| Document Parsing | Python (PyMuPDF, python-docx) |
| Backend | FastAPI |
| Frontend | Vanilla JS — dark theme, real-time GPU status bar |
| Deployment | Docker Compose |

Current hardware: NVIDIA RTX 5090 (32GB VRAM)

---

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- SSH tunnel to your GPU server running Ollama (see [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md))
- GPU with sufficient VRAM on the remote server (16GB+ recommended for Qwen3.5 9B)

### Run

```bash
git clone https://github.com/ailabph/vault-docs.git
cd vault-docs
docker compose up
```

Open `http://localhost:3000` (or your VPS IP on port `APP_PORT`) in your browser.

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
  Ollama (Qwen3.5 9B)
  ┌─────────────────┐
  │  Summary        │
  │  Key Points     │
  │  Q&A context    │
  └─────────────────┘
        │
        ▼
   Web Interface
   (private infrastructure only)
```

No data reaches a cloud provider or third-party service. Document text travels from your browser to a privately hosted VPS, then to a privately owned GPU server via encrypted SSH tunnel. Nothing touches a public cloud.

---

## Configuration

Edit `.env` (or `docker-compose.yml` environment) to change the model. Edit `APP_PORT` in `.env` to change the public port:

```bash
# .env
OLLAMA_MODEL=qwen3.5:9b      # swap for any model you have pulled
APP_PORT=3000                 # public frontend port (used in ports: mapping)
GPU_LABEL=RTX 5090 · 32GB VRAM  # shown in the UI status bar
```

To use a different model:

```bash
ollama pull mistral
# then set OLLAMA_MODEL=mistral in .env
```

### Swapping GPU Servers

The app is designed for easy GPU server swaps — update the SSH tunnel, change `GPU_LABEL` in `.env`, and rebuild. See [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) for details.

---

## Performance

Tested on a 10-page PDF with Qwen3.5 9B:

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

`Powered by Qwen3.5 9B - No external APIs`
