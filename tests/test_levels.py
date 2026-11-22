from __future__ import annotations

import pytest

from hopscope.range.levels import A0, get_level
from hopscope.tools.caps import Mandate


def test_a0_grants_requested_even_beyond_held() -> None:
    held = Mandate.of("fs:read:/workspace/*")
    requested = Mandate.of("secrets:get:*")
    assert A0().grant(held, requested) == requested
    assert A0.enforce_tools is False


def test_get_level() -> None:
    assert isinstance(get_level("A0"), A0)
    with pytest.raises(ValueError, match="unknown level"):
        get_level("L9")


def test_attenuate_keeps_only_covered() -> None:
    from hopscope.range.levels import attenuate

    held = Mandate.of("fs:read:/workspace/*", "secrets:get:api_key")
    req = Mandate.of("fs:read:/workspace/a", "secrets:get:*", "net:post:x")
    assert attenuate(held, req) == Mandate.of("fs:read:/workspace/a")


def test_a1_attenuates_and_binds_tools() -> None:
    from hopscope.range.levels import A1

    held = Mandate.of("fs:read:/workspace/*")
    assert A1().grant(held, Mandate.of("fs:read:/workspace/*", "secrets:get:*")) == held
    assert A1.enforce_tools is True and isinstance(get_level("A1"), A1)
