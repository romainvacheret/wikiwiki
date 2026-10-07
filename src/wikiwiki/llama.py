from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .index import BookResult


DEFAULT_URL = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_MODEL = "ggml-org/gemma-4-E4B-it-GGUF:Q8_0"
REQUEST_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class Source:
    identifier: str
    title: str
    chapter: str
    page: int

    def label(self) -> str:
        return f"[{self.identifier}] {self.title} — {self.chapter} — page {self.page}"


@dataclass(frozen=True)
class Answer:
    text: str
    sources: tuple[Source, ...]


def source_entries(
    results: list[BookResult],
    max_pages: int = 10,
) -> list[tuple[Source, str]]:
    entries = []
    for result in results:
        for match in result.pages:
            source = Source(
                identifier=f"S{len(entries) + 1}",
                title=result.title,
                chapter=match.chapter,
                page=match.page,
            )
            entries.append((source, match.snippet))
            if len(entries) >= max_pages:
                return entries
    return entries


def _context(results: list[BookResult], max_pages: int = 10) -> str:
    return "\n\n".join(
        f"[{source.identifier}] {source.title} — {source.chapter} — page {source.page}\n{snippet}"
        for source, snippet in source_entries(results, max_pages)
    )


def _prompt(
    topic: str,
    results: list[BookResult],
    history: list[tuple[str, str]] | None = None,
) -> str:
    previous = ""
    if history:
        previous = "\n\nPrevious conversation:\n" + "\n\n".join(
            f"User: {question}\nAssistant: {response}"
            for question, response in history
        )
    return f"""Answer the user's question using only the provided excerpts.
If the excerpts do not contain enough information, say so clearly.
Do not invent facts or sources. Cite every factual claim with one or more source IDs such as [S1].
Use only the source IDs provided below.

User question:
{topic}{previous}

Source excerpts:
{_context(results)}
"""


class LlamaClient:
    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
    ):
        self.url = url or os.environ.get("WIKIWIKI_LLAMA_URL", DEFAULT_URL)
        self.model = model or os.environ.get("WIKIWIKI_LLAMA_MODEL", DEFAULT_MODEL)
        self.timeout = timeout

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 700,
            "stream": False,
            "reasoning_effort": "none",
            "reasoning_format": "none",
        }
        request = Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = self._request(request)
        return self._content(response)

    def _request(self, request: Request) -> dict:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                try:
                    return json.loads(response.read())
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
            raise RuntimeError(f"Could not reach llama.cpp at {self.url}: {exc.reason}") from exc
        except OSError as exc:
            raise RuntimeError(f"Could not read the llama.cpp response: {exc}") from exc

    @staticmethod
    def _content(response: dict) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("llama.cpp returned an unexpected response") from exc
        if not isinstance(content, str) or not content.strip():
            choice = response.get("choices", [{}])[0] if isinstance(response, dict) else {}
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
            fields = ", ".join(sorted(message)) if isinstance(message, dict) else "unknown"
            usage = response.get("usage", {}) if isinstance(response, dict) else {}
            raise RuntimeError(
                "llama.cpp returned empty content "
                f"(finish_reason={finish_reason!r}, message_fields=[{fields}], usage={usage})."
            )
        return content.strip()


def answer(
    topic: str,
    results: list[BookResult],
    history: list[tuple[str, str]] | None = None,
) -> Answer:
    client = LlamaClient()
    content = client.complete(
        [
            {"role": "system", "content": "You are a careful research assistant."},
            {"role": "user", "content": _prompt(topic, results, history)},
        ]
    )
    entries = source_entries(results)
    return Answer(content, tuple(source for source, _ in entries))


__all__ = [
    "Answer",
    "DEFAULT_MODEL",
    "DEFAULT_URL",
    "LlamaClient",
    "REQUEST_TIMEOUT_SECONDS",
    "Source",
    "_context",
    "_prompt",
    "answer",
]
