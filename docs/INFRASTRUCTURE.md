# Infrastructure

## Hardware

| Resource | Spec |
|---|---|
| GPUs | 4x NVIDIA RTX A5000 |
| Total VRAM | 96GB |
| Primary Model | Qwen3 32B |
| Deployment Target | Single-node, on-premises |

## Services (Docker Compose)

```
vault-docs
├── frontend        Nginx serving static HTML/CSS/JS  :3000
├── backend         FastAPI (Python)                  :8000
└── ollama          Ollama inference server            :11434
```

All services are internal to the Docker network. Only the frontend port (`3000`) is exposed to the host. The backend and Ollama are not publicly accessible.

## Network Topology

```
Host Machine
│
├── :3000  →  frontend (Nginx)
│                │
│                └── /api/*  →  backend:8000 (FastAPI)
│                                    │
│                                    └── ollama:11434 (Ollama)
│
└── No outbound connections
```

No traffic leaves the host. DNS resolution, model downloads, and all inference are local.

## Ollama

- Runs as a Docker service with GPU passthrough (`deploy.resources.reservations.devices`)
- Model pulled at container startup via `ollama pull qwen3:32b`
- API endpoint: `http://ollama:11434` (internal Docker DNS)
- Model is configurable via `OLLAMA_MODEL` environment variable

## Volumes

| Volume | Purpose |
|---|---|
| `ollama-models` | Persists pulled models across container restarts |
| `./uploads` | Temporary document storage during processing (in-memory preferred) |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `qwen3:32b` | Model name passed to Ollama |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama API base URL |
| `APP_PORT` | `3000` | Frontend exposed port |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum document upload size |

## GPU Passthrough (Docker Compose)

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

Requires `nvidia-container-toolkit` installed on the host.

## After Initial Setup

Once models are pulled, the stack runs fully offline. No internet connection required for operation.
