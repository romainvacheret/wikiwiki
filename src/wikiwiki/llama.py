from __future__ import annotations

import json
import os
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .index import BookResult


DEFAULT_URL = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_MODEL = "ggml-org/gemma-4-E4B-it-GGUF:Q8_0"
REQUEST_TIMEOUT_SECONDS = 300


def _context(results: list[BookResult], max_pages: int = 10) -> str:
    excerpts = []
    for result in results:
        for match in result.pages:
            excerpts.append(
                f"[{result.title} — {match.chapter} — page {match.page}]\n{match.snippet}"
            )
            if len(excerpts) >= max_pages:
                return "\n\n".join(excerpts)
    return "\n\n".join(excerpts)


def answer(topic: str, results: list[BookResult]) -> str:
    prompt = f"""Answer the user's question using only the provided excerpts.
If the excerpts do not contain enough information, say so clearly.
Do not invent facts or sources. Mention the relevant book and chapter when useful.

User question:
{topic}

Source excerpts:
{_context(results)}
"""
    payload = {
        "model": os.environ.get("WIKIWIKI_LLAMA_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": "You are a careful research assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
        "stream": False,
        # Answers should be concise and usable as RAG output. Without this,
        # Gemma can spend the whole completion budget in reasoning_content.
        "reasoning_effort": "none",
        "reasoning_format": "none",
    }
    request = Request(
        os.environ.get("WIKIWIKI_LLAMA_URL", DEFAULT_URL),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            try:
                data = json.loads(response.read())
            except json.JSONDecodeError as exc:
                raise RuntimeError("llama.cpp returned invalid JSON") from exc
    except (socket.timeout, TimeoutError) as exc:
        raise RuntimeError(
            "llama.cpp did not respond within 5 minutes. "
            "The model may still be generating; check the llama.cpp server logs."
        ) from exc
    except HTTPError as exc:
        raise RuntimeError(f"llama.cpp returned HTTP error {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach llama.cpp at {request.full_url}: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not read the llama.cpp response: {exc}") from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("llama.cpp returned an unexpected response") from exc
    if not isinstance(content, str) or not content.strip():
        choice = data.get("choices", [{}])[0] if isinstance(data, dict) else {}
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        fields = ", ".join(sorted(message)) if isinstance(message, dict) else "unknown"
        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        raise RuntimeError(
            "llama.cpp returned empty content "
            f"(finish_reason={finish_reason!r}, message_fields=[{fields}], usage={usage})."
        )
    return content.strip()
