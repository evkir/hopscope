from __future__ import annotations

import json

import pytest
from a2a.helpers import new_text_message

from hopscope.range.a2a_bridge.cards import card_for, hop_url
from hopscope.range.a2a_bridge.codec import (
    MANDATE_EXT,
    ROLE_USER,
    CodecError,
    envelope_to_message,
    message_to_envelope,
    result_from_text,
    result_to_text,
)
from hopscope.range.envelope import AgentResult, TaskEnvelope
from hopscope.tools.caps import Mandate

ENV = TaskEnvelope("r1", 2, "planner", "read it", Mandate.of("net:fetch:a", "fs:read:/w/*"), ("page",))


def test_envelope_roundtrip() -> None:
    msg = envelope_to_message(ENV)
    assert msg.role == ROLE_USER and MANDATE_EXT in msg.extensions
    assert message_to_envelope(msg) == ENV


def _with_meta(meta: dict) -> object:
    msg = new_text_message("x", role=ROLE_USER)
    msg.metadata.update({"hopscope": meta})
    return msg


GOOD = {"run_id": "r", "hop": 1, "sender": "s", "mandate": [], "context": []}


@pytest.mark.parametrize(
    "patch",
    [{"hop": -1}, {"hop": 1.5}, {"hop": "1"}, {"run_id": ""}, {"mandate": "fs:read:*"}, {"mandate": ["bogus:a:b"]}, {"context": [1]}],
)
def test_bad_metadata_rejected(patch: dict) -> None:
    with pytest.raises(CodecError):
        message_to_envelope(_with_meta({**GOOD, **patch}))  # type: ignore[arg-type]


def test_missing_metadata_rejected() -> None:
    with pytest.raises(CodecError, match="missing"):
        message_to_envelope(new_text_message("x", role=ROLE_USER))


def test_result_roundtrip_nested() -> None:
    leaf = AgentResult("executor", True, outputs=[{"seq": 0, "result": ["a"]}])
    root = AgentResult("planner", False, errors=["e"], children=[leaf])
    assert result_from_text(result_to_text(root)) == root


@pytest.mark.parametrize("text", ["nope", "[]", json.dumps({"agent": "a", "ok": "yes"}), "[" * 100_000])
def test_bad_result_rejected(text: str) -> None:
    with pytest.raises(CodecError):
        result_from_text(text)


def test_card_declares_mandate_extension() -> None:
    card = card_for("worker")
    assert card.supported_interfaces[0].url == hop_url("worker") == "http://worker.hopscope.test/"
    assert card.capabilities.extensions[0].uri == MANDATE_EXT and not card.capabilities.streaming


def test_token_survives_the_wire() -> None:
    env = TaskEnvelope("r1", 2, "planner", "read it", Mandate(), (), "abc.def")
    assert message_to_envelope(envelope_to_message(env)).token == "abc.def"
    assert message_to_envelope(envelope_to_message(ENV)).token is None


def test_non_string_token_rejected() -> None:
    with pytest.raises(CodecError, match="token"):
        message_to_envelope(_with_meta({**GOOD, "token": 5}))  # type: ignore[arg-type]
