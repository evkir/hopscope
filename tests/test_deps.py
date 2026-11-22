from __future__ import annotations

import importlib.metadata as md


def test_a2a_sdk_major_is_1() -> None:
    assert md.version("a2a-sdk").split(".")[0] == "1"


def test_server_and_client_stack_importable() -> None:
    import a2a.client
    import a2a.server.routes  # noqa: F401
    import starlette.applications  # noqa: F401
