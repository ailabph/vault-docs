"""Tests for llm.py — Ollama client, prompt building, response parsing."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from llm import _build_chat_messages, _parse_analysis, analyze, chat

_DUMMY_REQUEST = httpx.Request("POST", "http://localhost/api/chat")


def _ok_response(content: str) -> httpx.Response:
    """Build a mock 200 Ollama response with a request attached."""
    return httpx.Response(
        200,
        json={"message": {"role": "assistant", "content": content}},
        request=_DUMMY_REQUEST,
    )


# --- Response parsing ---


class TestParseAnalysis:
    def test_well_formed_response(self):
        raw = (
            "SUMMARY: This document discusses climate change impacts.\n"
            "It covers three main areas.\n\n"
            "KEY POINTS:\n"
            "- Rising sea levels threaten coastal cities\n"
            "- Temperature increases affect agriculture\n"
            "- Biodiversity loss accelerates"
        )
        result = _parse_analysis(raw)
        assert "climate change" in result["summary"]
        assert len(result["key_points"]) == 3
        assert "Rising sea levels" in result["key_points"][0]

    def test_summary_only(self):
        raw = "SUMMARY: A brief document about testing."
        result = _parse_analysis(raw)
        assert "testing" in result["summary"]
        assert result["key_points"] == []

    def test_key_points_only(self):
        raw = "KEY POINTS:\n- Point one\n- Point two"
        result = _parse_analysis(raw)
        assert result["summary"] == ""
        assert len(result["key_points"]) == 2

    def test_no_structure_fallback(self):
        raw = "This is just a plain text response with no labels."
        result = _parse_analysis(raw)
        assert result["summary"] == raw.strip()
        assert result["key_points"] == []

    def test_empty_response(self):
        result = _parse_analysis("")
        assert result["summary"] == ""
        assert result["key_points"] == []

    def test_malformed_partial(self):
        raw = "SUMMARY: Partial summary here\nKEY POINTS:\n"
        result = _parse_analysis(raw)
        assert "Partial summary" in result["summary"]
        assert result["key_points"] == []


# --- Chat message construction ---


class TestBuildChatMessages:
    def test_basic_construction(self):
        msgs = _build_chat_messages("doc text", [], "What is this about?")
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert msgs[1]["content"] == "doc text"
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "What is this about?"
        assert len(msgs) == 3

    def test_with_history(self):
        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]
        msgs = _build_chat_messages("doc text", history, "Follow up?")
        assert len(msgs) == 5  # system + context + 2 history + question
        assert msgs[2]["role"] == "user"
        assert msgs[2]["content"] == "First question"
        assert msgs[3]["role"] == "assistant"
        assert msgs[-1]["content"] == "Follow up?"


# --- analyze() with mocked Ollama ---


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_returns_structured_dict(self):
        mock_response = _ok_response(
            "SUMMARY: Test document about AI.\n\n"
            "KEY POINTS:\n- AI is transformative\n- Ethics matter"
        )
        with patch("llm.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await analyze("Some document text")

        assert "AI" in result["summary"]
        assert len(result["key_points"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_malformed_response_no_crash(self):
        mock_response = _ok_response("Just some unstructured text.")
        with patch("llm.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await analyze("Some text")

        assert result["summary"] == "Just some unstructured text."
        assert result["key_points"] == []


# --- chat() with mocked Ollama ---


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_returns_answer(self):
        mock_response = _ok_response("The document discusses testing.")
        with patch("llm.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await chat("doc context", [], "What is it about?")

        assert result == "The document discusses testing."


# --- Malformed Ollama response ---


class TestMalformedOllamaResponse:
    @pytest.mark.asyncio
    async def test_missing_message_key_raises_value_error(self):
        bad_response = httpx.Response(
            200,
            json={"unexpected": "structure"},
            request=_DUMMY_REQUEST,
        )
        with patch("llm.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=bad_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(ValueError, match="Unexpected Ollama response format"):
                await analyze("some text")


# --- Timeout ---


class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_raises_exception(self):
        with patch("llm.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("timed out")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(httpx.TimeoutException):
                await analyze("Some text")

    @pytest.mark.asyncio
    async def test_chat_timeout_raises(self):
        with patch("llm.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("timed out")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(httpx.TimeoutException):
                await chat("ctx", [], "question")
