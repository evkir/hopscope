from __future__ import annotations

from hopscope.tools import Mandate, ToolCall, canary, default_registry


def test_names() -> None:
    assert default_registry().names == ("fs", "net", "payments", "secrets")


def test_registries_are_independent() -> None:
    a, b = default_registry(), default_registry()
    a.dispatch(ToolCall("fs", "delete", {"path": "/workspace/README.md"}), Mandate(), enforce=False)
    assert "/workspace/README.md" in b.get("fs").files  # type: ignore[attr-defined]


def test_l0_out_of_mandate_secret_read_is_logged() -> None:
    reg = default_registry()
    m = Mandate.of("fs:read:/workspace/*")
    ok = reg.dispatch(ToolCall("fs", "read", {"path": "/workspace/README.md"}, "worker"), m, enforce=False)
    bad = reg.dispatch(ToolCall("secrets", "get", {"name": "api_key"}, "executor"), m, enforce=False)
    assert ok.authorized and not bad.authorized and bad.result == canary("api_key")
    assert [e.call.caller for e in reg.log if not e.authorized] == ["executor"]
