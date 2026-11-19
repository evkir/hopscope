from __future__ import annotations

import socket
from typing import NoReturn

import pytest


def _blocked(*_a: object, **_k: object) -> NoReturn:
    raise RuntimeError("network access is forbidden in hopscope tests (mark with @pytest.mark.live)")


@pytest.fixture(autouse=True)
def _no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
