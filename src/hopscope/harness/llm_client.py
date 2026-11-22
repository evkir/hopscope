"""LLM backends: deterministic (scripted, CI) and live (Ollama).

The Ollama path follows the run executor of the PPD pre-registration v0.5 (§5):
the server is asked neither to truncate a conversation that does not fit nor to
shift the context under a reply (``truncate``/``shift`` off); models run at their
shipped sampling parameters unless a temperature is set; a seed of 0 is refused
because a backend may read it as unset; every model can be unloaded before an
agent starts. CyberAI's TrustGuard is deliberately NOT in this path: a guard in
the LLM call would confound what hopscope measures. Defences enter only through
attenuation levels A1/A2.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import urlsplit

Message = Mapping[str, str]
#: (url, JSON payload or None for GET, timeout) -> (HTTP status, body)
Transport = Callable[[str, dict[str, Any] | None, float], tuple[int, bytes]]

OVERFLOW_ERROR = "exceed_context_size_error"

#: Models and reasoning switches selected for collection in PPD v0.5 §5 (Pilot result).
LIVE_MODELS: tuple[tuple[str, bool | None], ...] = (
    ("granite4.1:8b", None),
    ("gemma4:12b", False),
    ("qwen3:14b", False),
)


class LLMError(RuntimeError):
    """Backend failure: unreachable, bad status, malformed or exhausted output."""


class LLMContextOverflow(LLMError):
    """The request does not fit in num_ctx. Deterministic: the same request is refused again."""


class LLMTruncated(LLMError):
    """The reply stopped at num_predict or at the end of the context (done_reason 'length')."""


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
    """One live model. temperature None keeps the shipped sampling; think None sends no switch."""

    model: str = "qwen3:14b"
    think: bool | None = False
    base_url: str = "http://localhost:11434"
    temperature: float | None = None
    seed: int | None = None
    num_ctx: int = 8192
    num_predict: int = 8192
    timeout: float = 300.0
    extra_options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        parts = urlsplit(self.base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError(f"ollama base_url must be http(s)://host, got {self.base_url!r}")
        if self.seed is not None and (type(self.seed) is not int or self.seed < 1):
            raise ValueError("seed must be a positive integer; 0 may be read as unset by the backend")
        for name in ("num_ctx", "num_predict"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")

    def with_seed(self, seed: int) -> OllamaConfig:
        return replace(self, seed=seed)


def urllib_transport(url: str, payload: dict[str, Any] | None, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(  # noqa: S310 — scheme validated in OllamaConfig
        url,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
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

    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}{path}"

    def build_request(
        self,
        messages: list[dict[str, str]],
        system: str | None,
        schema: Mapping[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        full = ([{"role": "system", "content": system}] if system else []) + list(messages)
        options: dict[str, Any] = {
            "num_ctx": self.config.num_ctx,
            "num_predict": self.config.num_predict,
            **self.config.extra_options,
        }
        if self.config.temperature is not None:
            options["temperature"] = self.config.temperature
        if self.config.seed is not None:
            options["seed"] = self.config.seed
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": full,
            "stream": False,
            "options": options,
            "truncate": False,
            "shift": False,
        }
        if self.config.think is not None:
            payload["think"] = self.config.think
        if schema is not None:
            payload["format"] = schema_all_required(schema)
        return self._url("/api/chat"), payload

    def _failure(self, status: int, body: bytes) -> LLMError:
        detail = body.decode("utf-8", errors="replace")[:300]
        if status == 400 and OVERFLOW_ERROR in detail:
            return LLMContextOverflow(f"ollama: request does not fit in num_ctx={self.config.num_ctx}: {detail}")
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
        if data.get("done_reason") == "length":
            raise LLMTruncated(
                f"ollama: reply cut off (num_predict={self.config.num_predict}, num_ctx={self.config.num_ctx})"
            )
        return content, int(data.get("prompt_eval_count", 0)), int(data.get("eval_count", 0))

    def _request_json(self, path: str, payload: dict[str, Any] | None) -> Any:
        status, body = self._transport(self._url(path), payload, self.config.timeout)
        if status != 200:
            raise self._failure(status, body)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMError(f"ollama {path}: reply is not JSON") from exc

    def loaded_models(self) -> list[str]:
        data = self._request_json("/api/ps", None)
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise LLMError("ollama /api/ps: no model list")
        names: list[str] = []
        for entry in models:
            name = (entry.get("name") or entry.get("model")) if isinstance(entry, dict) else None
            if not isinstance(name, str) or not name:
                raise LLMError("ollama /api/ps: a loaded model carries no name")
            names.append(name)
        return names

    def unload(
        self,
        *,
        wait_s: float = 60.0,
        poll_s: float = 0.2,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Unload every model the server holds and return once none is left (PPD v0.5 §5)."""
        for name in self.loaded_models():
            self._request_json("/api/generate", {"model": name, "keep_alive": 0})
        deadline = clock() + wait_s
        while self.loaded_models():
            if clock() >= deadline:
                raise LLMError(f"ollama still holds a model {wait_s:g} s after unload")
            sleep(poll_s)


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
