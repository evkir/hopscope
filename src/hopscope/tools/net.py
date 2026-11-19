"""Simulated network: canned pages for fetch, outbox for post. Never opens a socket."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from hopscope.tools.base import SimTool, ToolCall, ToolError, get_arg
from hopscope.tools.caps import Domain


def url_host(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise ToolError(f"net: bad url {url!r}") from exc
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ToolError(f"net: url must be http(s) with host, got {url!r}")
    return parts.hostname


class SimNet(SimTool):
    name = "net"
    domain = Domain.NET
    actions = frozenset({"fetch", "post"})

    def __init__(self, pages: Mapping[str, str] | None = None) -> None:
        self.pages: dict[str, str] = dict(pages or {})
        self.outbox: list[tuple[str, str]] = []

    def resource(self, call: ToolCall) -> str:
        return url_host(get_arg(call, "url"))

    def execute(self, call: ToolCall) -> Any:
        url = get_arg(call, "url")
        url_host(url)
        if call.action == "fetch":
            if url in self.pages:
                return {"status": 200, "body": self.pages[url]}
            return {"status": 404, "body": ""}
        self.outbox.append((url, get_arg(call, "body")))
        return {"status": 202}
