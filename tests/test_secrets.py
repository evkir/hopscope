from __future__ import annotations

import pytest

from hopscope.tools.base import ToolCall, ToolError
from hopscope.tools.caps import Capability, Mandate
from hopscope.tools.secrets import CANARY_PREFIX, SimSecrets


def test_get_returns_canary() -> None:
    v = SimSecrets().execute(ToolCall("secrets", "get", {"name": "api_key"}))
    assert v == CANARY_PREFIX + "api_key"


def test_list_needs_wildcard_resource() -> None:
    req = SimSecrets().required(ToolCall("secrets", "list"))
    assert req == Capability.parse("secrets:list:*")
    assert not Mandate.of("secrets:list:db_*").allows(req)


def test_put_then_get_and_missing() -> None:
    s = SimSecrets(names=())
    s.execute(ToolCall("secrets", "put", {"name": "k", "value": "v"}))
    assert s.execute(ToolCall("secrets", "get", {"name": "k"})) == "v"
    with pytest.raises(ToolError):
        s.execute(ToolCall("secrets", "get", {"name": "nope"}))
