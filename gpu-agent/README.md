# GPU Agent

Lightweight HTTP service that wraps `nvidia-smi` and exposes GPU hardware info as JSON.

## Requirements

- Python 3.6+ (stdlib only — no pip installs)
- `nvidia-smi` available in PATH (NVIDIA drivers installed)

## Usage

```bash
# Start the agent (default: 127.0.0.1:5111)
python3 gpu_agent.py

# Custom host/port
python3 gpu_agent.py --host 0.0.0.0 --port 5111
```

## Endpoints

### `GET /gpu-status`

Returns GPU hardware info:

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
  "summary": "NVIDIA RTX 5090 · 32GB VRAM",
  "cached_at": "2026-03-12T08:30:00Z"
}
```

If `nvidia-smi` is not found:

```json
{
  "ok": false,
  "error": "nvidia-smi not found",
  "gpus": [],
  "gpu_count": 0
}
```

### `GET /health`

Returns `{"status": "ok"}`.

## Caching

Results are cached for 2 seconds to avoid stalling under load.

## Deployment

### As a systemd service

```ini
[Unit]
Description=GPU Status Agent
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/gpu-agent/gpu_agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### SSH Tunnel

Add to `ollama-tunnel.service`:

```
-L 127.0.0.1:5111:localhost:5111
```
