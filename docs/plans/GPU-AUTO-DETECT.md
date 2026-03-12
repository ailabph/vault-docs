# Plan: Auto-Detect GPU Hardware via nvidia-smi

**Author:** Roxie (Claude Opus)
**Date:** March 12, 2026
**Status:** Draft — updated with Pavianne's review feedback

---

## Goal

Automatically detect GPU hardware (card names, count, VRAM, utilization, temperature) from the remote GPU server so the UI status bar displays real hardware info without manual `GPU_LABEL` configuration.

---

## Current State

- `GPU_LABEL` is a static string in `.env` (e.g. `RTX 5090 · 32GB VRAM`)
- Ollama API only reports per-model memory usage, not GPU hardware details
- No mechanism to query the GPU server's actual hardware

---

## Proposed Architecture

```
Browser (polls /api/status every 5s)
    │
    ▼
Backend (FastAPI)
    │
    ├── Ollama API (/api/ps, /api/tags) ← existing, via SSH tunnel
    │
    └── GPU Agent API (new) ← lightweight service on GPU server
            │
            ▼
        nvidia-smi (on GPU server)
```

---

## Approach: Lightweight GPU Agent on GPU Server

### Why not SSH from the backend?

- Backend runs inside Docker — no SSH keys, no direct access to GPU server
- Piping SSH commands through the VPS host adds complexity and security surface
- SSH per-request is slow and fragile

### Why a GPU agent?

- Tiny HTTP service running on the GPU server alongside Ollama
- Exposes a single endpoint: `GET /gpu-status`
- Parses `nvidia-smi` output into JSON
- Tunneled to VPS the same way Ollama is — one extra `-L` flag in the SSH tunnel

---

## Implementation Plan

### Phase 1: GPU Agent (Python script on GPU server)

**File:** `gpu-agent/gpu_agent.py`

A minimal FastAPI/Flask app (or even raw `http.server`) that:

1. Runs `nvidia-smi --query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu --format=csv,noheader,nounits`
2. Parses CSV output into structured JSON
3. Serves it on `localhost:5111` (or similar unused port)
4. **Caches nvidia-smi output for 2 seconds** — serves last sample between refreshes for smoother behavior under load
5. **Returns structured error if nvidia-smi is unavailable** — `{ "ok": false, "error": "nvidia-smi not found" }` so backend can log and fall back cleanly

**Response format (success):**
```json
{
  "ok": true,
  "gpus": [
    {
      "index": 0,
      "uuid": "GPU-a1b2c3d4-...",
      "name": "NVIDIA RTX 5090",
      "vram_total_mb": 32768,
      "vram_used_mb": 9728,
      "vram_free_mb": 23040,
      "utilization_percent": 0,
      "temperature_c": 43
    }
  ],
  "gpu_count": 1,
  "total_vram_mb": 32768,
  "summary": "1x RTX 5090 · 32GB VRAM",
  "cached_at": "2026-03-12T08:30:00Z"
}
```

**Response format (error):**
```json
{
  "ok": false,
  "error": "nvidia-smi not found",
  "gpus": [],
  "gpu_count": 0
}
```

**Dependencies:** None beyond Python stdlib (use `subprocess` + `http.server`). No pip installs needed.

**Run as:** systemd service on GPU server, or just `nohup python3 gpu_agent.py &`

### Phase 2: Extend SSH Tunnel

Add a second port forward to the existing `ollama-tunnel.service`:

```ini
ExecStart=/usr/bin/ssh -i /root/.ssh/vastai_rsa \
    -p 37825 \
    -L 127.0.0.1:11434:localhost:11434 \
    -L 127.0.0.1:5111:localhost:5111 \
    -N -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=60 \
    -o ExitOnForwardFailure=yes \
    root@85.91.153.130
```

The backend can then reach the GPU agent at `host.docker.internal:5111`.

### Phase 3: Backend Integration

**Changes to `backend/main.py`:**

1. Add new config var: `GPU_AGENT_HOST` (default: `http://host.docker.internal:5111`)
2. In `/api/status`, query the GPU agent alongside Ollama:
   - `GET {GPU_AGENT_HOST}/gpu-status` (timeout: 3s)
   - If reachable → use live GPU data, ignore `GPU_LABEL`
   - If unreachable → fall back to static `GPU_LABEL` from `.env`
3. Merge GPU agent data into the existing status response

**Updated `/api/status` response:**
```json
{
  "ollama": "reachable",
  "configured_model": "qwen3.5:9b",
  "gpu_label": "1x RTX 5090 · 32GB VRAM",
  "gpu_source": "live",
  "gpus": [
    {
      "name": "NVIDIA RTX 5090",
      "vram_total_mb": 32768,
      "vram_used_mb": 9728,
      "vram_free_mb": 23040,
      "utilization_percent": 0,
      "temperature_c": 43
    }
  ],
  "running_models": [...],
  "available_models": [...]
}
```

`gpu_source` is `"live"` when GPU agent is reachable, `"static"` when falling back to `GPU_LABEL`.

### Phase 4: Frontend Updates

Update the status bar to display live GPU data when available:

1. **GPU hardware label** — auto-generated from live data (e.g. "1x RTX 5090 · 32GB VRAM") or static fallback
2. **Per-GPU cards** (when multiple GPUs) — show each GPU's utilization and VRAM usage
3. **Temperature badge** — color-coded (green < 60°C, yellow < 80°C, red ≥ 80°C)
4. **Utilization bar** — real GPU compute % (not just VRAM)
5. **Live indicator** — small "LIVE" badge when `gpu_source === "live"`, "STATIC" when using fallback

### Phase 5: Docker Compose Update

Add `GPU_AGENT_HOST` to backend environment:

```yaml
backend:
  environment:
    - GPU_AGENT_HOST=${GPU_AGENT_HOST:-http://host.docker.internal:5111}
```

---

## File Changes Summary

| File | Change |
|---|---|
| `gpu-agent/gpu_agent.py` | **New** — lightweight nvidia-smi HTTP wrapper |
| `gpu-agent/README.md` | **New** — setup instructions for GPU server |
| `backend/config.py` | Add `GPU_AGENT_HOST` env var |
| `backend/main.py` | Query GPU agent in `/api/status`, fallback to `GPU_LABEL` |
| `frontend/app.js` | Render live GPU cards with temp + utilization |
| `frontend/style.css` | Styles for GPU cards, temp badges |
| `frontend/index.html` | Minor — update status bar structure if needed |
| `docker-compose.yml` | Add `GPU_AGENT_HOST` to backend env |
| `ollama-tunnel.service` | Add `-L 0.0.0.0:5111:localhost:5111` |
| `docs/INFRASTRUCTURE.md` | Document GPU agent setup |

---

## Rollout Steps

1. Deploy `gpu_agent.py` on GPU server, verify `curl localhost:5111/gpu-status`
2. Update SSH tunnel to forward port 5111, restart tunnel
3. Verify from VPS: `curl localhost:5111/gpu-status`
4. Deploy backend + frontend changes
5. Confirm status bar shows live GPU data

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| GPU agent not running on new server | Graceful fallback to static `GPU_LABEL` — UI still works |
| Tunnel doesn't forward port 5111 | Same fallback — `gpu_source: "static"` in response |
| nvidia-smi not installed | GPU agent returns error, backend falls back |
| Polling overhead (every 5s) | GPU agent is < 1ms to respond; nvidia-smi is ~10ms. Negligible |
| Security — exposing GPU metrics | Agent listens on localhost only, tunneled via SSH bound to 127.0.0.1. No public exposure |
| nvidia-smi stalls under load | 2s cache in GPU agent — serves last sample, never blocks on nvidia-smi |
| GPU reordering across reboots | Each GPU tracked by `uuid` for stable identity |

---

## When to Swap GPU Servers (Updated Workflow)

1. Deploy `gpu_agent.py` on the new GPU server
2. Update `ollama-tunnel.service` with new IP/port (both 11434 and 5111)
3. Restart tunnel: `systemctl restart ollama-tunnel`
4. Pull model: `ollama pull qwen3.5:9b`
5. **No `.env` changes needed** — GPU label auto-detected

If the new server doesn't have the GPU agent, just set `GPU_LABEL` in `.env` as before. The system degrades gracefully.

---

## Open Questions

1. **Should the GPU agent be Python or a shell script?** Python is more portable and structured, but a shell script with `nvidia-smi` + `nc` would have zero dependencies. *(Leaning Python — need caching logic anyway.)*
2. ~~**Should we cache nvidia-smi output?**~~ **Resolved: Yes, 2s cache.** (Per Pavianne's review.)
3. **Multi-GPU display** — when there are 4 GPUs, should we show all 4 individually or a summary? Both?
4. **Should we include power draw?** nvidia-smi can report wattage — useful or noise?

---

## Estimated Effort

| Phase | Time |
|---|---|
| GPU Agent script | 30 min |
| Tunnel update | 5 min |
| Backend integration | 30 min |
| Frontend updates | 45 min |
| Testing + docs | 30 min |
| **Total** | **~2.5 hours** |
