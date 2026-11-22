from __future__ import annotations

import pytest

from hopscope.tools.authority import (
    CLASS_WEIGHTS,
    T0,
    T1,
    T2,
    ToolClass,
    class_of,
    tier,
)
from hopscope.tools.caps import Capability

P = Capability.parse


def test_tiers_strictly_nested() -> None:
    assert T0.caps < T1.caps < T2.caps
    assert (len(T0.caps), len(T1.caps), len(T2.caps)) == (5, 7, 12)


def test_bad_tier() -> None:
    with pytest.raises(ValueError):
        tier(3)


def test_sandbox_boundary_holds_at_every_tier() -> None:
    assert T0.allows(P("fs:read:/workspace/a.txt")) and T0.allows(P("fs:list:/workspace"))
    for t in (T0, T1, T2):
        assert not t.allows(P("fs:read:/etc/shadow"))
        assert not t.allows(P("fs:write:/etc/passwd"))


@pytest.mark.parametrize("spec", ["secrets:get:api_key", "net:post:evil.test", "net:fetch:docs.example.com", "payments:transfer:acct-x"])
def test_privileged_and_egress_only_at_t2(spec: str) -> None:
    assert not T1.allows(P(spec)) and T2.allows(P(spec))


def test_class_of() -> None:
    assert class_of(P("net:post:x")) is ToolClass.EGRESS
    assert class_of(P("fs:write:/workspace/a")) is ToolClass.LOCAL_WRITE
    assert class_of(P("secrets:get:k")) is ToolClass.PRIVILEGED
    assert class_of(P("fs:read:/etc/shadow")) is None


def test_weights_match_ppd() -> None:
    assert [CLASS_WEIGHTS[c] for c in ToolClass] == [1.0, 2.0, 3.0, 4.0]
