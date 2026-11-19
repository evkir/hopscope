from __future__ import annotations

from typing import Any

import pytest

from hopscope.tools.base import SimTool, ToolCall, ToolError, get_arg
from hopscope.tools.caps import Domain, Mandate
from hopscope.tools.registry import ToolRegistry


class Echo(SimTool):
    name = "echo"
    domain = Domain.NET
    actions = frozenset({"say", "boom"})

    def resource(self, call: ToolCall) -> str:
        return get_arg(call, "to")

    def execute(self, call: ToolCall) -> Any:
        if call.action == "boom":
            raise ToolError("boom")
        return call.args["to"]


ALLOW = Mandate.of("net:say:ok")


def test_unknown_tool_and_action() -> None:
    reg = ToolRegistry([Echo()])
    with pytest.raises(ToolError):
        reg.dispatch(ToolCall("nope", "say", {"to": "ok"}), ALLOW, enforce=True)
    with pytest.raises(ToolError):
        reg.dispatch(ToolCall("echo", "nope", {"to": "ok"}), ALLOW, enforce=True)


def test_duplicate_tool_rejected() -> None:
    with pytest.raises(ValueError):
        ToolRegistry([Echo(), Echo()])


def test_authorized_executes() -> None:
    ev = ToolRegistry([Echo()]).dispatch(ToolCall("echo", "say", {"to": "ok"}), ALLOW, enforce=True)
    assert ev.authorized and ev.executed and ev.result == "ok" and ev.error is None


def test_l0_unauthorized_still_executes_but_is_flagged() -> None:
    ev = ToolRegistry([Echo()]).dispatch(ToolCall("echo", "say", {"to": "evil"}), ALLOW, enforce=False)
    assert ev.executed and not ev.authorized and str(ev.required) == "net:say:evil"


def test_enforced_unauthorized_is_denied() -> None:
    ev = ToolRegistry([Echo()]).dispatch(ToolCall("echo", "say", {"to": "evil"}), ALLOW, enforce=True)
    assert not ev.executed and ev.error == "denied: net:say:evil"


def test_tool_error_captured_and_seq_increments() -> None:
    reg = ToolRegistry([Echo()])
    reg.dispatch(ToolCall("echo", "say", {"to": "ok"}), ALLOW, enforce=False)
    ev = reg.dispatch(ToolCall("echo", "boom", {"to": "ok"}), Mandate.of("net:*:*"), enforce=True)
    assert ev.seq == 1 and not ev.executed and ev.error == "boom"
    assert [e.seq for e in reg.log] == [0, 1]


@pytest.mark.parametrize("args", [{}, {"to": ""}, {"to": 1}])
def test_get_arg_rejects_bad_str(args: dict[str, Any]) -> None:
    with pytest.raises(ToolError):
        get_arg(ToolCall("echo", "say", args), "to")


def test_get_arg_rejects_bool_as_int() -> None:
    with pytest.raises(ToolError):
        get_arg(ToolCall("p", "t", {"n": True}), "n", int)
