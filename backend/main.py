"""FastAPI application — vault-docs backend."""

import json
import re

import httpx
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

import llm
import parser
import session
from config import GPU_AGENT_HOST, GPU_LABEL, MAX_UPLOAD_SIZE_MB, OLLAMA_HOST, OLLAMA_MODEL

app = FastAPI(title="vault-docs", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str
    question: str


@app.get("/api/health")
async def health():
    """Return backend status and Ollama reachability.

    Returns 200 only when Ollama is reachable (readiness check).
    Returns 503 when Ollama is down so Docker HEALTHCHECK fails correctly.
    """
    ollama_status = "unreachable"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            if resp.status_code == 200:
                ollama_status = "reachable"
    except Exception:
        pass

    if ollama_status == "unreachable":
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "ollama": "unreachable"},
        )

    return {"status": "ok", "ollama": "reachable", "model": OLLAMA_MODEL}


@app.get("/api/status")
async def system_status():
    """Return real-time GPU/model status from Ollama + GPU agent."""
    result = {
        "ollama": "unreachable",
        "configured_model": OLLAMA_MODEL,
        "gpu_label": GPU_LABEL,
        "gpu_source": "static",
        "gpus": [],
        "running_models": [],
        "available_models": [],
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # ── GPU Agent (live hardware info) ─────────────────────
            try:
                gpu_resp = await client.get(
                    f"{GPU_AGENT_HOST}/gpu-status", timeout=3.0
                )
                if gpu_resp.status_code == 200:
                    gpu_data = gpu_resp.json()
                    if gpu_data.get("ok"):
                        result["gpus"] = gpu_data.get("gpus", [])
                        result["gpu_label"] = gpu_data.get("summary", GPU_LABEL)
                        result["gpu_source"] = "live"
                    else:
                        # Agent responded but nvidia-smi unavailable
                        import logging
                        logging.warning(
                            "GPU agent error: %s", gpu_data.get("error", "unknown")
                        )
            except Exception:
                pass  # GPU agent unreachable — fall back to static GPU_LABEL

            # ── Ollama: running models ─────────────────────────────
            try:
                ps_resp = await client.get(f"{OLLAMA_HOST}/api/ps")
                if ps_resp.status_code == 200:
                    ps_data = ps_resp.json()
                    models = ps_data.get("models", [])
                    for m in models:
                        size_vram = m.get("size_vram", 0)
                        size = m.get("size", 0)
                        gpu_pct = round((size_vram / size * 100), 1) if size > 0 else 0
                        running = {
                            "name": m.get("name", "unknown"),
                            "size": _format_bytes(size),
                            "size_vram": _format_bytes(size_vram),
                            "gpu_percent": gpu_pct,
                            "expires_at": m.get("expires_at", ""),
                            "details": {
                                "family": m.get("details", {}).get("family", ""),
                                "parameter_size": m.get("details", {}).get("parameter_size", ""),
                                "quantization": m.get("details", {}).get("quantization_level", ""),
                            },
                        }
                        result["running_models"].append(running)
            except Exception:
                pass

            # ── Ollama: available models ───────────────────────────
            try:
                tags_resp = await client.get(f"{OLLAMA_HOST}/api/tags")
                if tags_resp.status_code == 200:
                    tags_data = tags_resp.json()
                    for m in tags_data.get("models", []):
                        result["available_models"].append({
                            "name": m.get("name", ""),
                            "size": _format_bytes(m.get("size", 0)),
                            "parameter_size": m.get("details", {}).get("parameter_size", ""),
                            "family": m.get("details", {}).get("family", ""),
                            "quantization": m.get("details", {}).get("quantization_level", ""),
                        })
                    result["ollama"] = "reachable"
            except Exception:
                pass

    except Exception:
        pass

    return result


def _format_bytes(b: int) -> str:
    """Format bytes to human-readable string."""
    if b <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    """Upload a document for analysis. Returns summary and key points."""
    # --- size check ---
    content = await file.read()
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        return JSONResponse(
            status_code=413,
            content={"error": f"File exceeds {MAX_UPLOAD_SIZE_MB}MB size limit."},
        )
    # Reset file position so parser can read it
    await file.seek(0)

    # --- parse ---
    try:
        text = parser.extract_text(file)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    truncated = parser.truncate(text)

    # --- LLM analysis ---
    try:
        result = await llm.analyze(truncated)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError, ValueError):
        return JSONResponse(
            status_code=503,
            content={"error": "Document analysis service is temporarily unavailable. Please try again."},
        )

    # --- session ---
    sid = session.create_session(truncated)

    return {
        "session_id": sid,
        "summary": result["summary"],
        "key_points": result["key_points"],
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Ask a follow-up question about an analyzed document (SSE streaming)."""
    # --- session lookup (before streaming starts → normal JSON error) ---
    try:
        sess = session.get_session(req.session_id)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found. Please upload a document first."},
        )

    async def event_stream():
        full_answer: list[str] = []
        try:
            async for token, done in llm.chat_stream(
                context=sess["document_text"],
                history=sess["chat_history"],
                question=req.question,
            ):
                full_answer.append(token)
                payload = json.dumps({"token": token, "done": done})
                yield f"data: {payload}\n\n"
                if done:
                    break
        except (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.HTTPStatusError,
            ValueError,
        ):
            error_payload = json.dumps({"error": "Service unavailable"})
            yield f"data: {error_payload}\n\n"
            return

        # Persist both turns after stream completes — strip <think> blocks
        # so internal reasoning is not resent to the model on follow-up turns
        assembled = "".join(full_answer)
        cleaned = re.sub(r"<think>.*?</think>", "", assembled, flags=re.DOTALL).strip()
        session.append_message(req.session_id, "user", req.question)
        session.append_message(req.session_id, "assistant", cleaned)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
