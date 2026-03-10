"""Ollama LLM client — prompt building and inference calls."""

import json
import re
from collections.abc import AsyncGenerator

import httpx

from config import OLLAMA_HOST, OLLAMA_MODEL

_TIMEOUT = 300.0

ANALYSIS_SYSTEM = "You are a document analysis assistant. Be concise and accurate."

ANALYSIS_USER_TEMPLATE = """Analyze the following document.
Return exactly:
SUMMARY: <3-5 sentence summary>
KEY POINTS:
- <point>
- <point>
...

Document:
{text}"""

CHAT_SYSTEM = (
    "You are answering questions about a document provided by the user. "
    "Only use information from the document. If the answer is not in the document, say so."
)


async def _call_ollama(messages: list[dict]) -> str:
    """Send messages to Ollama /api/chat and return the assistant content."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
            },
        )
        resp.raise_for_status()
        try:
            return resp.json()["message"]["content"]
        except (KeyError, ValueError) as e:
            raise ValueError(f"Unexpected Ollama response format: {e}") from e


def _parse_analysis(raw: str) -> dict:
    """Parse Ollama plain-text response into {summary, key_points}.

    Handles missing sections gracefully — returns best-effort output.
    """
    summary = ""
    key_points: list[str] = []

    # Extract summary
    summary_match = re.search(
        r"SUMMARY:\s*(.*?)(?=KEY\s*POINTS:|$)", raw, re.DOTALL | re.IGNORECASE
    )
    if summary_match:
        summary = summary_match.group(1).strip()

    # Extract key points
    kp_match = re.search(r"KEY\s*POINTS:\s*(.*)", raw, re.DOTALL | re.IGNORECASE)
    if kp_match:
        kp_block = kp_match.group(1)
        key_points = [
            line.lstrip("-•*").strip()
            for line in kp_block.strip().splitlines()
            if line.strip() and line.strip().lstrip("-•*").strip()
        ]

    # Fallback: if no structured sections found, use entire response as summary
    if not summary and not key_points:
        summary = raw.strip()

    return {"summary": summary, "key_points": key_points}


async def analyze(text: str) -> dict:
    """Analyze document text. Returns {summary: str, key_points: list[str]}."""
    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM},
        {"role": "user", "content": ANALYSIS_USER_TEMPLATE.format(text=text)},
    ]
    raw = await _call_ollama(messages)
    return _parse_analysis(raw)


def _build_chat_messages(
    context: str, history: list[dict], question: str
) -> list[dict]:
    """Build the messages array for a multi-turn chat request."""
    messages = [
        {"role": "system", "content": CHAT_SYSTEM},
        {"role": "user", "content": context},
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": question})
    return messages


async def chat(context: str, history: list[dict], question: str) -> str:
    """Send a chat question with document context and history. Returns answer string."""
    messages = _build_chat_messages(context, history, question)
    return await _call_ollama(messages)


async def chat_stream(
    context: str, history: list[dict], question: str
) -> AsyncGenerator[tuple[str, bool], None]:
    """Stream chat tokens from Ollama. Yields (token, done) tuples.

    Raises httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError
    on failure — caller is responsible for handling.
    """
    messages = _build_chat_messages(context, history, question)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": True,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                done = chunk.get("done", False)
                yield (token, done)
