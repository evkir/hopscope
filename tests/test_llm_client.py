from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

import pytest

from hopscope.harness.llm_client import (
    LIVE_MODELS,
    LLMContextOverflow,
    LLMError,
    LLMTruncated,
    OllamaBackend,
    OllamaConfig,
    ScriptedBackend,
    make_backend,
    schema_all_required,
)

SCHEMA = {"type": "object", "properties": {"b": {"type": "string"}, "a": {"type": "integer"}}, "required": ["a"]}


class FakeServer:
    """Per-path queues of (status, body); the last response of a queue repeats."""

    def __init__(self, routes: dict[str, list[tuple[int, Any]]]) -> None:
        self.routes = {k: list(v) for k, v in routes.items()}
        self.calls: list[tuple[str, Any, float]] = []

    def __call__(self, url: str, payload: Any, timeout: float) -> tuple[int, bytes]:
        self.calls.append((url, payload, timeout))
        queue = self.routes[urlsplit(url).path]
        status, body = queue.pop(0) if len(queue) > 1 else queue[0]
        return status, body if isinstance(body, bytes) else json.dumps(body).encode()


def chat_server(status: int, body: Any) -> FakeServer:
    return FakeServer({"/api/chat": [(status, body)]})


def test_scripted_order_usage_transcript() -> None:
    b = ScriptedBackend({"planner": ["one two", "three"]})
    msgs = [{"role": "user", "content": "do the task"}]
    assert b.chat(msgs, agent="planner") == "one two"
    msgs[0]["content"] = "mutated"
    assert b.chat([{"role": "user", "content": "x"}], agent="planner") == "three"
    assert b.usage.calls == 2 and b.usage.prompt_tokens == 4 and b.usage.completion_tokens == 3
    assert b.transcript[0]["messages"][0]["content"] == "do the task"
    with pytest.raises(LLMError, match="no reply left"):
        b.chat(msgs, agent="planner")
    with pytest.raises(LLMError):
        b.chat(msgs, agent="worker")


def test_chat_json() -> None:
    b = ScriptedBackend({"w": ['{"a": 1}', "not json", "[1]"]})
    assert b.chat_json([], SCHEMA, agent="w") == {"a": 1}
    with pytest.raises(LLMError, match="not JSON"):
        b.chat_json([], SCHEMA, agent="w")
    with pytest.raises(LLMError, match="not an object"):
        b.chat_json([], SCHEMA, agent="w")


def test_schema_all_required_is_copy() -> None:
    out = schema_all_required(SCHEMA)
    assert out["required"] == ["a", "b"] and SCHEMA["required"] == ["a"]
    assert schema_all_required({"type": "object"}) == {"type": "object"}


def test_request_shape_follows_ppd_executor() -> None:
    b = OllamaBackend(OllamaConfig(base_url="http://h:11434/", seed=7))
    url, p = b.build_request([{"role": "user", "content": "q"}], "sys", SCHEMA)
    assert url == "http://h:11434/api/chat"
    assert p["messages"][0] == {"role": "system", "content": "sys"}
    assert p["options"] == {"num_ctx": 8192, "num_predict": 8192, "seed": 7}
    assert p["truncate"] is False and p["shift"] is False and p["think"] is False
    assert p["model"] == "qwen3:14b" and p["stream"] is False and p["format"]["required"] == ["a", "b"]


def test_temperature_and_think_are_optional() -> None:
    cfg = OllamaConfig(model="granite4.1:8b", think=None, temperature=0.2)
    _, p = OllamaBackend(cfg).build_request([], None, None)
    assert p["options"] == {"num_ctx": 8192, "num_predict": 8192, "temperature": 0.2}
    assert "think" not in p and "format" not in p and p["messages"] == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seed": 0},
        {"seed": -1},
        {"seed": True},
        {"num_ctx": 0},
        {"num_predict": 1.5},
        {"base_url": "file:///etc/passwd"},
        {"base_url": "localhost:11434"},
        {"base_url": "http://"},
    ],
)
def test_config_rejects(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        OllamaConfig(**kwargs)


def test_with_seed_is_a_validated_copy() -> None:
    base = OllamaConfig()
    assert base.with_seed(42).seed == 42 and base.seed is None
    with pytest.raises(ValueError):
        base.with_seed(0)


def test_success_counts_usage() -> None:
    body = {"message": {"content": "hi"}, "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 2}
    srv = chat_server(200, body)
    b = OllamaBackend(transport=srv)
    assert b.chat([{"role": "user", "content": "q"}], agent="worker") == "hi"
    assert (b.usage.prompt_tokens, b.usage.completion_tokens) == (5, 2)
    assert srv.calls[0][2] == 300.0


@pytest.mark.parametrize(
    ("status", "body", "exc", "match"),
    [
        (404, b"model not found", LLMError, "ollama pull qwen3:14b"),
        (500, b"boom", LLMError, "HTTP 500"),
        (200, b"{}", LLMError, "malformed"),
        (400, b'{"error":"exceed_context_size_error"}', LLMContextOverflow, "num_ctx=8192"),
        (200, json.dumps({"message": {"content": "par"}, "done_reason": "length"}).encode(), LLMTruncated, "cut off"),
    ],
)
def test_failures(status: int, body: bytes, exc: type[Exception], match: str) -> None:
    with pytest.raises(exc, match=match):
        OllamaBackend(transport=chat_server(status, body)).chat([])


def test_unload_every_loaded_model_and_wait() -> None:
    srv = FakeServer({
        "/api/ps": [(200, {"models": [{"name": "qwen3:14b"}, {"model": "gemma4:12b"}]}), (200, {"models": []})],
        "/api/generate": [(200, {})],
    })
    OllamaBackend(transport=srv).unload(sleep=lambda _s: None)
    gens = [p for u, p, _ in srv.calls if u.endswith("/api/generate")]
    assert gens == [{"model": "qwen3:14b", "keep_alive": 0}, {"model": "gemma4:12b", "keep_alive": 0}]
    assert all(p is None for u, p, _ in srv.calls if u.endswith("/api/ps"))


def test_unload_times_out() -> None:
    srv = FakeServer({"/api/ps": [(200, {"models": [{"name": "x"}]})], "/api/generate": [(200, {})]})
    ticks = iter(range(100))
    with pytest.raises(LLMError, match="still holds"):
        OllamaBackend(transport=srv).unload(wait_s=3, sleep=lambda _s: None, clock=lambda: float(next(ticks)))


def test_loaded_models_rejects_nameless_entry() -> None:
    with pytest.raises(LLMError, match="no name"):
        OllamaBackend(transport=FakeServer({"/api/ps": [(200, {"models": [{}]})]})).loaded_models()


def test_live_models_match_ppd_selection() -> None:
    assert LIVE_MODELS == (("granite4.1:8b", None), ("gemma4:12b", False), ("qwen3:14b", False))


def test_make_backend() -> None:
    assert isinstance(make_backend("deterministic"), ScriptedBackend)
    assert isinstance(make_backend("live", guard=False), OllamaBackend)
    with pytest.raises(ValueError):
        make_backend("bogus")


def test_fresh_load_unloads_before_each_agent_turn() -> None:
    from hopscope.harness.llm_client import FreshLoadOllama

    body = {"message": {"content": "{}"}, "done_reason": "stop"}
    srv = FakeServer({"/api/chat": [(200, body)], "/api/ps": [(200, {"models": []})]})
    b = FreshLoadOllama(transport=srv)
    for agent in ("orchestrator", "planner", "planner", "worker", "executor", "worker"):
        b.chat([], agent=agent)
    assert b.unloads == 5
    paths = [urlsplit(u).path for u, _, _ in srv.calls]
    assert paths[0] == "/api/ps" and paths.count("/api/chat") == 6
