from __future__ import annotations

import socket
from typing import NoReturn

import pytest


def _blocked(*_a: object, **_k: object) -> NoReturn:
    raise RuntimeError(
        "network access is forbidden in hopscope tests (mark with @pytest.mark.live; dvaa allows loopback only)"
    )


_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


def _loopback_connect(real):
    def connect(self, address, *a, **k):
        if not (isinstance(address, tuple) and address[0] in _LOOPBACK):
            _blocked()
        return real(self, address, *a, **k)

    return connect


def _loopback_resolve(real):
    def getaddrinfo(host, *a, **k):
        if host not in _LOOPBACK:
            _blocked()
        return real(host, *a, **k)

    return getaddrinfo


@pytest.fixture(autouse=True)
def _no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("live"):
        return
    if request.node.get_closest_marker("dvaa"):
        monkeypatch.setattr(socket.socket, "connect", _loopback_connect(socket.socket.connect))
        monkeypatch.setattr(socket.socket, "connect_ex", _loopback_connect(socket.socket.connect_ex))
        monkeypatch.setattr(socket, "getaddrinfo", _loopback_resolve(socket.getaddrinfo))
        return
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
