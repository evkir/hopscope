from __future__ import annotations

import pytest

from hopscope.range.levels import L0, get_level
from hopscope.tools.caps import Mandate


def test_l0_grants_requested_even_if_inflated() -> None:
    held = Mandate.of("fs:read:/workspace/*")
    requested = Mandate.of("secrets:get:*")
    assert L0().grant(held, requested) == requested
    assert L0.enforce_tools is False


def test_get_level() -> None:
    assert isinstance(get_level("L0"), L0)
    with pytest.raises(ValueError, match="unknown level"):
        get_level("L9")
