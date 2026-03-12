#!/usr/bin/env python3
"""Lightweight GPU status agent — wraps nvidia-smi as JSON over HTTP.

Run on the GPU server alongside Ollama. Listens on localhost:5111.
No dependencies beyond Python 3 stdlib.

Usage:
    python3 gpu_agent.py [--port 5111] [--host 127.0.0.1]
"""

import json
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Cache ───────────────────────────────────────────────────────────
_cache = {"data": None, "ts": 0}
CACHE_TTL = 2.0  # seconds


def query_gpus():
    """Run nvidia-smi and parse output into structured JSON."""
    now = time.time()

    # Return cached data if fresh
    if _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "nvidia-smi not found",
            "gpus": [],
            "gpu_count": 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "nvidia-smi timed out",
            "gpus": [],
            "gpu_count": 0,
        }

    if result.returncode != 0:
        return {
            "ok": False,
            "error": f"nvidia-smi exited with code {result.returncode}",
            "gpus": [],
            "gpu_count": 0,
        }

    gpus = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 8:
            continue
        gpus.append({
            "index": int(parts[0]),
            "uuid": parts[1],
            "name": parts[2],
            "vram_total_mb": int(parts[3]),
            "vram_used_mb": int(parts[4]),
            "vram_free_mb": int(parts[5]),
            "utilization_percent": int(parts[6]),
            "temperature_c": int(parts[7]),
        })

    total_vram = sum(g["vram_total_mb"] for g in gpus)

    # Build summary string
    if gpus:
        name_counts = {}
        for g in gpus:
            name_counts[g["name"]] = name_counts.get(g["name"], 0) + 1
        parts = []
        for name, count in name_counts.items():
            parts.append(f"{count}x {name}" if count > 1 else name)
        vram_gb = total_vram / 1024
        summary = " + ".join(parts) + f" · {vram_gb:.0f}GB VRAM"
    else:
        summary = ""

    data = {
        "ok": True,
        "gpus": gpus,
        "gpu_count": len(gpus),
        "total_vram_mb": total_vram,
        "summary": summary,
        "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Update cache
    _cache["data"] = data
    _cache["ts"] = now

    return data


class GPUHandler(BaseHTTPRequestHandler):
    """Handle GET /gpu-status requests."""

    def do_GET(self):
        if self.path == "/gpu-status" or self.path == "/gpu-status/":
            data = query_gpus()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        elif self.path == "/health" or self.path == "/health/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default access logs — too noisy at 5s polling
        pass


def main():
    host = "127.0.0.1"
    port = 5111

    # Simple arg parsing
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
        elif arg == "--host" and i + 1 < len(args):
            host = args[i + 1]

    server = HTTPServer((host, port), GPUHandler)
    print(f"GPU Agent listening on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
