# vault-docs Expert Reference

## What It Is

Air-gapped document analyzer by aiLab.ph. Upload PDF/TXT/DOCX → get summary, key points, and chat Q&A. Zero cloud dependencies — all inference on private GPU via SSH tunnel.

**Repo:** `ailabph/vault-docs`
**License:** Apache 2.0
**Status:** Weekly Proof of Product #1, release target Friday March 14, 2026

---

## Architecture

```
Browser → Frontend (Nginx :3000) → Backend (FastAPI :8000) → SSH tunnel → GPU Server (Ollama :11434)
```

Two-server model:
- **VPS** (vault-docs, agent-farm-2, 192.168.122.12) — runs the web app in Docker
- **GPU Server** (vast.ai, 85.91.153.130:37825) — runs Ollama with RTX 5090

No data leaves the private infrastructure. Document text flows: browser → VPS (HTTPS) → GPU (SSH tunnel). No third-party APIs, no telemetry, no cloud.

---

## Infrastructure

| Component | Details |
|---|---|
| VPS | 8GB RAM, 4 vCPU, 40GB disk, Ubuntu 24.04 |
| VPS User | `vault` (passwordless sudo) |
| VPS SSH | `ssh vault-docs` (ProxyJump agent-farm-2) |
| GPU | NVIDIA RTX 5090, 32GB VRAM |
| GPU SSH | port 37825, key `/root/.ssh/vastai_rsa` |
| Model | qwen3.5:9b (Q4_K_M quantization) |
| Tunnel | systemd `ollama-tunnel.service`, binds `0.0.0.0:11434` |
| Docker | Frontend (:3000→80) + Backend (:8000 internal) |
| Autostart | VPS and tunnel both enabled |

### SSH Tunnel Service

```ini
# /etc/systemd/system/ollama-tunnel.service
ExecStart=/usr/bin/ssh -i /root/.ssh/vastai_rsa \
    -p 37825 \
    -L 0.0.0.0:11434:localhost:11434 \
    -N -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=60 \
    -o ExitOnForwardFailure=yes \
    root@85.91.153.130
Restart=always
RestartSec=10
```

Bound to `0.0.0.0` so Docker containers can reach it via `host.docker.internal:11434`.

---

## Stack

| Layer | Technology |
|---|---|
| LLM Inference | Ollama (qwen3.5:9b) |
| Backend | FastAPI + Uvicorn (Python 3.12) |
| PDF Parsing | PyMuPDF (`fitz`) |
| DOCX Parsing | python-docx |
| HTTP Client | httpx (async) |
| Frontend | Vanilla JS, CSS custom properties, dark theme |
| Frontend Server | Nginx (static + `/api/*` proxy to backend) |
| Deployment | Docker Compose |

---

## Backend Modules

### `main.py` — API Routes

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Readiness check — 200 if Ollama reachable, 503 if not |
| `/api/status` | GET | Real-time GPU/model status — running models, VRAM usage, GPU label, available models |
| `/api/analyze` | POST | Upload file → extract text → Ollama → summary + key points |
| `/api/chat` | POST | Q&A with document context + chat history |

Error codes: 400 (bad input), 404 (session not found), 413 (file too large), 503 (Ollama unavailable)

### `parser.py` — Text Extraction

- `.pdf` → PyMuPDF (`fitz`)
- `.docx` → python-docx
- `.txt` → UTF-8 decode
- Truncates to `MAX_WORDS_PROMPT` (default 8000 words) before LLM

### `llm.py` — Ollama Client

- `analyze(text)` → `{summary, key_points}` via structured prompt
- `chat(context, history, question)` → answer string
- Uses `/api/chat` endpoint (non-streaming)
- Timeout: 300s (5 minutes)
- Parses response with regex for `SUMMARY:` and `KEY POINTS:` sections

### `session.py` — In-Memory Sessions

- Dict keyed by UUID
- Stores `document_text` + `chat_history`
- No persistence, no TTL — lost on container restart
- Single-user demo scope

### `config.py` — Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `qwen3.5:9b` | Model name |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max upload size |
| `MAX_WORDS_PROMPT` | `8000` | Text truncation limit |
| `GPU_LABEL` | `RTX 5090 · 32GB VRAM` | GPU hardware label shown in UI status bar |

---

## Frontend

Three UI states: **Upload** → **Processing** → **Results + Chat**

- Vanilla JS (ES6+), no framework, no build step
- Dark theme with CSS custom properties (ailab.ph cyan accent `#00e5ff`)
- Nginx serves static files, proxies `/api/*` to `backend:8000`
- Required sovereignty messaging embedded in all states
- **Real-time status bar** (fixed bottom) — polls `/api/status` every 5s:
  - Connection indicator (green/red dot)
  - GPU hardware label (from `GPU_LABEL` env var)
  - Running model chips with VRAM usage bars (green/yellow/red)
  - Active model name
- `nginx.conf`: `proxy_read_timeout 120s` (may need bump for large docs)

---

## Docker Compose

```yaml
services:
  backend:
    build: ./backend
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - OLLAMA_HOST=${OLLAMA_HOST:-http://host.docker.internal:11434}
      - OLLAMA_MODEL=${OLLAMA_MODEL:-qwen3.5:35b}
      - MAX_UPLOAD_SIZE_MB=${MAX_UPLOAD_SIZE_MB:-50}
      - MAX_WORDS_PROMPT=${MAX_WORDS_PROMPT:-8000}
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "${APP_PORT:-3000}:80"
    depends_on:
      - backend
    restart: unless-stopped
```

---

## Current `.env` (VPS)

```
OLLAMA_HOST=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3.5:9b
MAX_UPLOAD_SIZE_MB=50
MAX_WORDS_PROMPT=8000
APP_PORT=3000
GPU_LABEL=RTX 5090 · 32GB VRAM
```

---

## Prompts

### Analysis
```
System: You are a document analysis assistant. Be concise and accurate.
User: Analyze the following document.
      Return exactly:
      SUMMARY: <3-5 sentence summary>
      KEY POINTS:
      - <point>
      ...
      Document: {text}
```

### Chat
```
System: You are answering questions about a document provided by the user.
        Only use information from the document. If the answer is not in the document, say so.
Messages: [system, document_context, chat_history..., user_question]
```

---

## Common Operations

### Rebuild & restart after code changes
```bash
ssh vault-docs "cd ~/vault-docs && docker compose up -d --build"
```

### Check tunnel status
```bash
ssh vault-docs "systemctl status ollama-tunnel"
```

### Restart tunnel
```bash
ssh vault-docs "sudo systemctl restart ollama-tunnel"
```

### View backend logs
```bash
ssh vault-docs "cd ~/vault-docs && docker logs vault-docs-backend-1 --tail 50"
```

### Test Ollama from VPS host
```bash
ssh vault-docs "curl -s http://localhost:11434/api/tags"
```

### Test Ollama from inside backend container
```bash
ssh vault-docs "docker exec vault-docs-backend-1 python3 -c \"
import urllib.request, json
r = urllib.request.urlopen('http://host.docker.internal:11434/api/tags', timeout=5)
print(json.loads(r.read()))
\""
```

### Pull a different model on GPU
```bash
ssh vault-docs "sudo ssh -i /root/.ssh/vastai_rsa -p 37825 root@85.91.153.130 'ollama pull <model>'"
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Inference service unavailable" (503) | Tunnel down or Ollama unreachable | `sudo systemctl restart ollama-tunnel` |
| Health check returns 503 | Same as above | Check `ss -tlnp | grep 11434` on VPS |
| Container can't reach Ollama | Tunnel bound to 127.0.0.1 | Must bind to `0.0.0.0` in tunnel service |
| Timeout on large documents | Default was 60s | `_TIMEOUT` in `llm.py` (currently 300s) |
| Nginx 504 gateway timeout | Nginx proxy timeout too low | Bump `proxy_read_timeout` in `nginx.conf` |
| GPU server unreachable | vast.ai instance stopped or IP changed | Check vast.ai dashboard, update tunnel service |

---

## Roadmap Status (as of March 12, 2026)

- **Phase 1 (Foundation):** ✅ Complete — infra, tunnel, Docker running
- **Phase 2 (Core):** In progress — today's target, end-to-end analysis working
- **Phase 3 (Polish):** Thu Mar 13 — UI complete, screenshot-ready
- **Phase 4 (Release):** Fri Mar 14 — GitHub publish, demo assets

---

## Key Design Decisions

1. **No cloud, ever** — sovereignty is the product's core value prop
2. **SSH tunnel over VPN** — simpler, no additional software on GPU server
3. **Vanilla JS frontend** — no build step, no node_modules, fast iteration
4. **In-memory sessions** — acceptable for single-user demo, no persistence needed
5. **Text truncation at 8000 words** — prevents context window overflow, noted in output
6. **Separate VPS and GPU** — VPS does no ML work, all compute on GPU server
7. **Docker Compose** — single `docker compose up` for the app, tunnel managed by systemd

---

## CI/CD

GitHub Actions deploys on push to `main`:
1. SSH into VPS
2. `git pull origin main`
3. `docker compose build`
4. `docker compose up -d`

Secrets needed: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_PORT`

GPU server and tunnel are not touched by the pipeline.
