# Infrastructure

## Two-Server Architecture

The application runs across two separate machines:

| Server | Role |
|---|---|
| **VPS** | Hosts the web app — frontend (Nginx) + backend (FastAPI) |
| **GPU Server** | Runs Ollama inference — 4x RTX A5000, 96GB VRAM |

---

## VPS Provisioning

The VPS does no ML work. All compute is on the GPU server. Requirements are modest.

### Minimum (demo / proof of product)

| Resource | Spec |
|---|---|
| CPU | 2 vCPUs |
| RAM | 2GB |
| Storage | 20GB SSD |
| Bandwidth | 100 Mbps |
| OS | Ubuntu 22.04 LTS |

### Recommended (stable, room to grow)

| Resource | Spec |
|---|---|
| CPU | 4 vCPUs |
| RAM | 4GB |
| Storage | 40GB SSD |
| Bandwidth | 200 Mbps |
| OS | Ubuntu 22.04 LTS |

### Rationale

- **RAM** — Docker + Nginx + FastAPI + text extraction libraries runs well under 1GB. 2GB is comfortable, 4GB gives headroom.
- **CPU** — PyMuPDF and python-docx are fast, CPU-light operations. No ML inference on this server.
- **Storage** — OS + Docker images (~2GB) + temp upload buffer. 20GB is sufficient.
- **Network** — Low latency between VPS and GPU server matters more than raw bandwidth. Co-locate in the same datacenter region to minimize SSH tunnel overhead and improve response times.

### Suggested Providers

DigitalOcean, Hetzner, Linode, Vultr. A $6–12/month instance covers the minimum spec. Hetzner offers the best value for European regions.

---

## Network Topology

```
User Browser
     │  HTTPS (TLS terminated at host-level reverse proxy)
     ▼
  VPS
  ┌─────────────────────────────┐
  │  Caddy/Nginx (host) :443    │  ← TLS termination (see TLS section)
  │      │ HTTP                  │
  │      ▼                      │
  │  frontend (Nginx) :3000     │  ← app container, HTTP only
  │      │ /api/*               │
  │      ▼                      │
  │  backend (FastAPI) :8000    │
  │      │ host.docker.internal:11434  │
  │      ▼                      │
  │  SSH Tunnel ─────────────────────────► GPU Server
  │  (port forward)             │          Ollama :11434
  └─────────────────────────────┘          Qwen3.5 35B
```

The backend container calls `http://host.docker.internal:11434` (resolved via `extra_hosts: host-gateway` in `docker-compose.yml`). This reaches the SSH tunnel bound on the VPS host's `localhost:11434`. The backend has no knowledge of the GPU server's IP — the tunnel makes the remote Ollama appear local to the VPS host.

---

## SSH Tunnel

### Establish tunnel

```bash
ssh -i ~/.ssh/vastai_rsa \
    -p 38511 \
    root@<gpu-server-ip> \
    -L 11434:localhost:11434 \
    -N
```

| Flag | Purpose |
|---|---|
| `-L 11434:localhost:11434` | Forward local `11434` → GPU server `localhost:11434` |
| `-N` | No remote command — tunnel only |
| `-i ~/.ssh/vastai_rsa` | SSH key for GPU server auth |
| `-p 38511` | Non-standard SSH port on GPU server |

> **Local dev note:** If port `11434` is already in use (e.g. a local Ollama instance), map to a different local port: `-L 11435:localhost:11434`. Then set `OLLAMA_HOST=http://localhost:11435` in your `.env`.

### Keep tunnel alive (production)

Run via `autossh` or a systemd service so it reconnects on drop:

```ini
# /etc/systemd/system/ollama-tunnel.service
[Unit]
Description=SSH tunnel to Ollama GPU server
After=network.target

[Service]
ExecStart=ssh -i /root/.ssh/vastai_rsa \
              -p 38511 \
              -L 11434:localhost:11434 \
              # VPS has no local Ollama — 11434 is free, no conflict
              -N -o ServerAliveInterval=60 \
              -o ExitOnForwardFailure=yes \
              root@<gpu-server-ip>
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable ollama-tunnel
systemctl start ollama-tunnel
```

---

## VPS Services (Docker Compose)

```
vault-docs (VPS)
├── frontend    Nginx — static files + API proxy    :3000 (public)
└── backend     FastAPI                             :8000 (internal)
```

Ollama is **not** in the VPS Docker Compose. It runs on the GPU server.

The backend container reaches the SSH tunnel on the VPS host via `host.docker.internal`. This keeps the container isolated while making the routing explicit in `docker-compose.yml`.

### Docker Compose — backend network access to tunnel

```yaml
backend:
  extra_hosts:
    - "host.docker.internal:host-gateway"
  environment:
    - OLLAMA_HOST=http://host.docker.internal:11434
```

`host-gateway` resolves to the Docker host's IP, so `host.docker.internal:11434` reaches the SSH tunnel bound on the VPS host. No `network_mode: host` required.

---

## GPU Server

Ollama runs directly on the GPU server (not in Docker, or in Docker with GPU passthrough).

```bash
# Pull model (one-time)
ollama pull qwen3.5:35b

# Ollama listens on localhost:11434 by default
# No exposure needed — SSH tunnel handles access from VPS
```

| Resource | Spec |
|---|---|
| GPUs | 4x NVIDIA RTX A5000 |
| Total VRAM | 96GB |
| Model | Qwen3.5 35B |
| Ollama port | 11434 (localhost only) |

---

## Environment Variables (VPS)

| Variable | Value | Description |
|---|---|---|
| `OLLAMA_MODEL` | `qwen3.5:35b` | Model name |
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Tunneled Ollama endpoint (via extra_hosts) |
| `APP_PORT` | `3000` | Public frontend port |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max upload size |

---

## Startup Order

1. Ensure SSH tunnel to GPU server is active
2. Confirm Ollama is running on GPU server (`curl localhost:11434`)
3. `docker compose up` on VPS

The backend will fail requests (503) if the tunnel is down — it does not queue or retry. The tunnel must be established before the app serves traffic.

---

## TLS Termination

The application containers serve HTTP only. For production deployment, TLS must be terminated **in front of** the frontend container — not inside it.

### Recommended approach

Use Caddy or Certbot + Nginx as a host-level reverse proxy:

```
Browser ──HTTPS──► Caddy/Nginx (host) ──HTTP──► frontend container (:3000)
```

#### Caddy (auto-TLS, simplest)

```
# /etc/caddy/Caddyfile
yourdomain.com {
    reverse_proxy localhost:3000
}
```

Caddy handles certificate provisioning and renewal automatically via Let's Encrypt.

#### Certbot + Nginx (manual setup)

Install Certbot on the VPS host, obtain a certificate for your domain, and configure a host-level Nginx site to proxy to `localhost:3000` with `ssl_certificate` and `ssl_certificate_key` directives.

### Why not inside the container?

The app container runs `nginx:alpine` serving static files and proxying `/api/*`. Adding TLS inside the container would couple certificate management to the application lifecycle and complicate `docker compose up`. A host-level reverse proxy keeps concerns separated and allows certificate renewal without restarting the stack.
