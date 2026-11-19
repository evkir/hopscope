from __future__ import annotations

import json
from typing import Any

import pytest

from hopscope.harness.llm_client import (
    LLMError,
    OllamaBackend,
    OllamaConfig,
    ScriptedBackend,
    make_backend,
    schema_all_required,
)

SCHEMA = {"type": "object", "properties": {"b": {"type": "string"}, "a": {"type": "integer"}}, "required": ["a"]}


def fake(status: int, body: Any, seen: list | None = None):
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()

    def transport(url: str, payload: dict, timeout: float) -> tuple[int, bytes]:
        if seen is not None:
            seen.append((url, payload, timeout))
        return status, raw

    return transport


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


def test_ollama_request_shape() -> None:
    b = OllamaBackend(OllamaConfig(base_url="http://h:11434/", seed=7))
    url, p = b.build_request([{"role": "user", "content": "q"}], "sys", SCHEMA)
    assert url == "http://h:11434/api/chat"
    assert p["messages"][0] == {"role": "system", "content": "sys"}
    assert p["options"] == {"num_ctx": 8192, "temperature": 0.0, "seed": 7}
    assert p["stream"] is False and p["format"]["required"] == ["a", "b"]
    _, p2 = OllamaBackend(OllamaConfig(seed=None)).build_request([], None, None)
    assert "seed" not in p2["options"] and "format" not in p2 and p2["messages"] == []


def test_ollama_success_counts_usage() -> None:
    seen: list = []
    body = {"message": {"content": "hi"}, "prompt_eval_count": 5, "eval_count": 2}
    b = OllamaBackend(transport=fake(200, body, seen))
    assert b.chat([{"role": "user", "content": "q"}], agent="worker") == "hi"
    assert (b.usage.prompt_tokens, b.usage.completion_tokens) == (5, 2)
    assert seen[0][2] == 120.0


@pytest.mark.parametrize(
    ("status", "body", "match"),
    [(404, b"model not found", "ollama pull qwen2.5-coder:14b"), (500, b"boom", "HTTP 500"), (200, b"{}", "malformed")],
)
def test_ollama_failures(status: int, body: bytes, match: str) -> None:
    with pytest.raises(LLMError, match=match):
        OllamaBackend(transport=fake(status, body)).chat([])


@pytest.mark.parametrize("url", ["file:///etc/passwd", "localhost:11434", "http://"])
def test_ollama_config_rejects_bad_url(url: str) -> None:
    with pytest.raises(ValueError):
        OllamaConfig(base_url=url)


def test_make_backend() -> None:
    assert isinstance(make_backend("deterministic"), ScriptedBackend)
    assert isinstance(make_backend("live"), OllamaBackend)
    with pytest.raises(ValueError):
        make_backend("bogus")


@pytest.mark.live
def test_live_ollama_is_deterministic_with_seed() -> None:
    b = OllamaBackend()
    msgs = [{"role": "user", "content": "Name one prime number between 10 and 20. One word."}]
    assert b.chat(msgs, agent="probe") == b.chat(msgs, agent="probe")
