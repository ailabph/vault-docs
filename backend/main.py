"""FastAPI application — vault-docs backend."""

import httpx
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import llm
import parser
import session
from config import MAX_UPLOAD_SIZE_MB, OLLAMA_HOST

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

    return {"status": "ok", "ollama": "reachable"}


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
    """Ask a follow-up question about an analyzed document."""
    # --- session lookup ---
    try:
        sess = session.get_session(req.session_id)
    except KeyError:
        return JSONResponse(
            status_code=404,
            content={"error": "Session not found. Please upload a document first."},
        )

    # --- LLM chat ---
    try:
        answer = await llm.chat(
            context=sess["document_text"],
            history=sess["chat_history"],
            question=req.question,
        )
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError, ValueError):
        return JSONResponse(
            status_code=503,
            content={"error": "Chat service is temporarily unavailable. Please try again."},
        )

    # --- persist both turns ---
    session.append_message(req.session_id, "user", req.question)
    session.append_message(req.session_id, "assistant", answer)

    return {"answer": answer}
