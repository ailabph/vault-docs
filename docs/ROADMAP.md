# Roadmap

**Project:** vault-docs — Air-Gapped Document Analyzer
**Release deadline:** Friday, March 14, 2026
**Owner:** Danny Rivera

---

## Overview

| Phase | Days | Goal |
|---|---|---|
| 1 — Foundation | Mon–Tue Mar 10–11 | Repo, infra, services running |
| 2 — Core | Wed Mar 12 | Document analysis working end-to-end |
| 3 — Polish | Thu Mar 13 | UI complete, tested, screenshot-ready |
| 4 — Release | Fri Mar 14 | Docs, GitHub publish, demo assets |

---

## Phase 1 — Foundation
**Mon–Tue, March 10–11**

### Goals
Get the skeleton running. All services up, talking to each other, with no application logic yet.

### Tasks

**GPU Server (one-time bootstrap)**
- [ ] Confirm Ollama is installed and running on GPU server
- [ ] Run `ollama pull qwen3.5:35b` — wait for model download to complete
- [ ] Verify: `curl localhost:11434/api/tags` returns the model

**VPS Setup**
- [ ] Provision VPS (Ubuntu 22.04, 4 vCPU / 4GB RAM)
- [ ] Install Docker + Docker Compose on VPS
- [ ] Add SSH key for GPU server to VPS (`~/.ssh/vastai_rsa`)
- [ ] Establish SSH tunnel from VPS to GPU server, confirm `localhost:11434` is reachable
- [ ] Set up systemd `ollama-tunnel.service` to keep tunnel persistent (see `docs/INFRASTRUCTURE.md`)
- [ ] Clone repo to VPS: `git clone https://github.com/ailabph/vault-docs.git`
- [ ] Copy `.env.sample` to `.env`, fill in values (`OLLAMA_HOST=http://host.docker.internal:11434`)

**Application Scaffold**
- [ ] Scaffold repo structure: `backend/`, `frontend/`, `docker-compose.yml`
- [ ] Write `docker-compose.yml` — frontend + backend, `extra_hosts: host-gateway`, env vars
- [ ] Write `backend/Dockerfile` and `frontend/Dockerfile`
- [ ] Confirm `docker compose up` starts both services with no errors on VPS
- [ ] `GET /api/health` returns 200 and confirms Ollama is reachable through tunnel
- [ ] `POST /api/analyze` stub returns mock response (no real parsing yet)

**CI/CD**
- [ ] Set up GitHub Actions secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_PORT` (see `docs/CICD.md`)
- [ ] Create `.github/workflows/deploy.yml` — deploy to VPS on push to `main`
- [ ] Verify first automated deploy succeeds

### Exit Criteria
GPU server has model loaded. VPS tunnel is stable. `docker compose up` starts cleanly. Health check passes. First GitHub Actions deploy succeeds.

---

## Phase 2 — Core Functionality
**Wed, March 12**

### Goals
Real documents go in, real analysis comes out.

### Tasks
- [ ] Implement `parser.py` — PDF (PyMuPDF), DOCX (python-docx), TXT
- [ ] Implement `llm.py` — async Ollama client, analysis prompt, response parser
- [ ] Implement `session.py` — in-memory session store keyed by UUID
- [ ] Wire `POST /api/analyze` — file upload → text extraction → Ollama → structured response
- [ ] Wire `POST /api/chat` — session lookup → context + history → Ollama → answer
- [ ] Test with real documents: PDF, DOCX, TXT (at least one each)
- [ ] Confirm summary is 3–5 sentences and key points are a clean bullet list
- [ ] Confirm chat Q&A uses document context correctly
- [ ] Confirm zero outbound connections (check with `tcpdump` or `ss` during a request)
- [ ] Validate 503 returned when tunnel is down

### Exit Criteria
Upload a 10-page PDF, receive summary + key points in under 30 seconds. Ask a follow-up question, get a grounded answer.

---

## Phase 3 — UI Polish & Testing
**Thu, March 13**

### Goals
Interface is complete, visually impressive, and all acceptance criteria are met.

### Tasks
- [ ] Build `index.html` + `style.css` — dark theme, CSS custom properties
- [ ] Upload state — drag-and-drop zone, click-to-browse, sovereignty messaging
- [ ] Processing state — spinner/indicator, reinforced "stays local" message
- [ ] Results state — summary block, key points list, chat interface, model attribution footer
- [ ] All required phrases present in UI (see `ACCEPTANCE-CRITERIA.md`)
- [ ] Error handling — inline messages for bad file type, size, server errors
- [ ] "Analyze another document" resets to upload state, clears session
- [ ] End-to-end test: PDF → analysis → 3 chat questions → reset → DOCX → analysis
- [ ] Test at 1920×1080 — confirm layout is screenshot-worthy
- [ ] Test in Chrome, Firefox, Edge
- [ ] Verify file size rejection (upload >50MB file)
- [ ] Verify unsupported format rejection (.xls, .png, etc.)

### Exit Criteria
All checkboxes in `docs/ACCEPTANCE-CRITERIA.md` are ticked. Interface looks good at 1080p.

---

## Phase 4 — Release
**Fri, March 14**

### Morning — Documentation & GitHub

- [ ] Finalize `README.md` — confirm quick start works from a clean clone
- [ ] Review all `docs/` files for accuracy against the built implementation
- [ ] Confirm `LICENSE` is Apache 2.0
- [ ] Confirm no secrets, API keys, or credentials in any committed file
- [ ] Tag release: `git tag v1.0.0 && git push origin v1.0.0`
- [ ] Create GitHub Release with changelog summary

### Afternoon — Demo Assets

- [ ] Record 30-second screen recording showing full flow (upload → summary → chat)
- [ ] Take high-quality screenshot at 1920×1080 for LinkedIn post
- [ ] Draft LinkedIn post copy referencing ailab.ph blog

### Exit Criteria
Public GitHub repo is live, tagged, and accessible. Demo video and screenshot ready for publication.

---

## Definition of Done

The release is complete when:

1. `git clone` + `docker compose up` works on a clean VPS with tunnel configured
2. All items in `docs/ACCEPTANCE-CRITERIA.md` pass
3. GitHub repository is public with `v1.0.0` tag
4. Demo video is recorded
5. LinkedIn screenshot is ready
