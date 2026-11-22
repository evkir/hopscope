"""LLM backends: deterministic (scripted, CI) and live (Ollama).

Derived from CyberAI core/llm_client.py: the Ollama request shape (temperature,
seed and num_ctx always sent), all-required schema widening and actionable 404
errors. CyberAI's TrustGuard is deliberately NOT in this path: hopscope measures
mandate inflation, and a guard in the LLM call would confound the measurement.
Defences enter only through attenuation levels L1/L2.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

Message = Mapping[str, str]
Transport = Callable[[str, dict[str, Any], float], tuple[int, bytes]]


class LLMError(RuntimeError):
    """Backend failure: unreachable, bad status, malformed or exhausted output."""


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMBackend(ABC):
    name: str = "abstract"

    def __init__(self) -> None:
        self.usage = Usage()
        self.transcript: list[dict[str, Any]] = []

    def chat(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        schema: Mapping[str, Any] | None = None,
        agent: str = "unknown",
    ) -> str:
        msgs = [dict(m) for m in messages]
        text, prompt_toks, completion_toks = self._complete(msgs, system, schema, agent)
        self.usage.calls += 1
        self.usage.prompt_tokens += prompt_toks
        self.usage.completion_tokens += completion_toks
        self.transcript.append({"agent": agent, "system": system, "messages": msgs, "reply": text})
        return text

    def chat_json(
        self,
        messages: Sequence[Message],
        schema: Mapping[str, Any],
        *,
        system: str | None = None,
        agent: str = "unknown",
    ) -> dict[str, Any]:
        text = self.chat(messages, system=system, schema=schema, agent=agent)
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"{self.name}: reply is not JSON: {text[:120]!r}") from exc
        if not isinstance(obj, dict):
            raise LLMError(f"{self.name}: reply JSON is not an object")
        return obj

    @abstractmethod
    def _complete(
        self,
        messages: list[dict[str, str]],
        system: str | None,
        schema: Mapping[str, Any] | None,
        agent: str,
    ) -> tuple[str, int, int]: ...


class ScriptedBackend(LLMBackend):
    """Deterministic backend: per-agent queue of canned replies."""

    name = "scripted"

    def __init__(self, script: Mapping[str, Sequence[str]] | None = None) -> None:
        super().__init__()
        self._queues: dict[str, list[str]] = {k: list(v) for k, v in (script or {}).items()}

    def _complete(self, messages, system, schema, agent):  # type: ignore[override]
        queue = self._queues.get(agent)
        if not queue:
            raise LLMError(f"scripted: no reply left for agent {agent!r}")
        reply = queue.pop(0)
        prompt = sum(len(m.get("content", "").split()) for m in messages)
        return reply, prompt, len(reply.split())


def schema_all_required(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Copy of schema with every declared property required (stops early-exit decoding)."""
    widened = dict(schema)
    props = schema.get("properties")
    if isinstance(props, dict) and props:
        widened["required"] = sorted(props)
    return widened


@dataclass(frozen=True)
class OllamaConfig:
    model: str = "qwen2.5-coder:14b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0
    seed: int | None = 0
    num_ctx: int = 8192
    timeout: float = 120.0
    extra_options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        parts = urlsplit(self.base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError(f"ollama base_url must be http(s)://host, got {self.base_url!r}")


def urllib_transport(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise LLMError(f"ollama unreachable at {url}: {exc.reason}") from exc


class OllamaBackend(LLMBackend):
    name = "ollama"

    def __init__(self, config: OllamaConfig | None = None, transport: Transport | None = None) -> None:
        super().__init__()
        self.config = config or OllamaConfig()
        self._transport = transport or urllib_transport

    def build_request(
        self,
        messages: list[dict[str, str]],
        system: str | None,
        schema: Mapping[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        full = ([{"role": "system", "content": system}] if system else []) + list(messages)
        options: dict[str, Any] = {
            "num_ctx": self.config.num_ctx,
            "temperature": self.config.temperature,
            **self.config.extra_options,
        }
        if self.config.seed is not None:
            options["seed"] = self.config.seed
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": full,
            "stream": False,
            "options": options,
        }
        if schema is not None:
            payload["format"] = schema_all_required(schema)
        return f"{self.config.base_url.rstrip('/')}/api/chat", payload

    def _failure(self, status: int, body: bytes) -> LLMError:
        detail = body.decode("utf-8", errors="replace")[:300]
        if status == 404:
            return LLMError(
                f"ollama has no model '{self.config.model}': run `ollama pull {self.config.model}`"
                f" or set another model. ({detail})"
            )
        return LLMError(f"ollama HTTP {status}: {detail}")

    def _complete(self, messages, system, schema, agent):  # type: ignore[override]
        url, payload = self.build_request(messages, system, schema)
        status, body = self._transport(url, payload, self.config.timeout)
        if status != 200:
            raise self._failure(status, body)
        try:
            data = json.loads(body)
            content = data["message"]["content"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise LLMError(f"ollama: malformed response {body[:120]!r}") from exc
        return content, int(data.get("prompt_eval_count", 0)), int(data.get("eval_count", 0))


def make_backend(
    mode: str,
    *,
    script: Mapping[str, Sequence[str]] | None = None,
    ollama: OllamaConfig | None = None,
) -> LLMBackend:
    if mode == "deterministic":
        return ScriptedBackend(script)
    if mode == "live":
        return OllamaBackend(ollama)
    raise ValueError(f"unknown mode {mode!r} (expected 'deterministic' or 'live')")
