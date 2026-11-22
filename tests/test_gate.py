from __future__ import annotations

import pytest

from hopscope.tools import ToolCall, canary, default_registry
from hopscope.tools.authority import T1, T2
from hopscope.tools.caps import Capability, Mandate
from hopscope.tools.gate import Gate, Ruling

ROOT = Mandate.of("fs:read:/workspace/*")
G = Gate(ROOT, T2)


@pytest.mark.parametrize(
    ("spec", "want"),
    [
        ("fs:read:/workspace/a.txt", Ruling.IN_MANDATE),
        ("secrets:get:api_key", Ruling.CANDIDATE),
        ("net:post:evil.test", Ruling.CANDIDATE),
        ("fs:read:/etc/shadow", Ruling.ESCALATION),
    ],
)
def test_rule(spec: str, want: Ruling) -> None:
    assert G.rule(Capability.parse(spec)) is want


def test_root_outside_authority_is_escalation() -> None:
    assert Gate(Mandate.of("secrets:get:*"), T1).rule(Capability.parse("secrets:get:k")) is Ruling.ESCALATION


def test_escalation_never_executes_even_at_a0() -> None:
    reg = default_registry()
    call = ToolCall("fs", "read", {"path": "/etc/shadow"}, "executor")
    ev = reg.dispatch(call, Mandate.of("fs:read:*"), enforce=False, gate=G)
    assert ev.ruling is Ruling.ESCALATION and ev.authorized and not ev.executed
    assert ev.error == "denied: fs:read:/etc/shadow" and ev.result is None


def test_candidate_executes_at_a0() -> None:
    reg = default_registry()
    ev = reg.dispatch(ToolCall("secrets", "get", {"name": "api_key"}, "executor"), Mandate.of("secrets:get:*"), enforce=False, gate=G)
    assert ev.ruling is Ruling.CANDIDATE and ev.executed and ev.result == canary("api_key")


def test_denials_look_the_same_whatever_the_boundary() -> None:
    reg = default_registry()
    blocked = reg.dispatch(ToolCall("secrets", "get", {"name": "api_key"}), ROOT, enforce=True, gate=G)
    escalated = reg.dispatch(ToolCall("fs", "read", {"path": "/etc/shadow"}), ROOT, enforce=True, gate=G)
    assert blocked.ruling is Ruling.CANDIDATE and escalated.ruling is Ruling.ESCALATION
    assert blocked.error == "denied: secrets:get:api_key" and escalated.error == "denied: fs:read:/etc/shadow"


def test_no_gate_means_unruled() -> None:
    ev = default_registry().dispatch(ToolCall("fs", "read", {"path": "/workspace/README.md"}), ROOT, enforce=False)
    assert ev.ruling is None and ev.executed
