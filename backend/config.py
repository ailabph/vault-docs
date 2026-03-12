"""Environment variable loading with sensible defaults."""

import os

OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3.5:35b")
MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
MAX_WORDS_PROMPT: int = int(os.getenv("MAX_WORDS_PROMPT", "8000"))
GPU_LABEL: str = os.getenv("GPU_LABEL", "RTX 5090 · 32GB VRAM")
