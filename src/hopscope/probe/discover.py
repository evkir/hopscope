"""Find an agent's card at the A2A well-known locations, newest revision first.

A2A 0.3+ publishes ``/.well-known/agent-card.json``; 0.2 and earlier (DVAA's scenario agents
among them) publish ``/.well-known/agent.json``. Both live at the host root, whatever path the
base URL carries. Only a 404 moves on to the next location; any other failure is final.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from hopscope.probe.card import ProbeCard
from hopscope.probe.fetch import FetchError, fetch_card
from hopscope.targets import check_target

WELL_KNOWN: tuple[str, ...] = ("/.well-known/agent-card.json", "/.well-known/agent.json")


def discover_card(
    base_url: str, *, allow_remote: bool = False, transport: httpx.BaseTransport | None = None
) -> ProbeCard:
    check_target(base_url, allow_remote=allow_remote)
    parts = urlsplit(base_url)
    root = f"{parts.scheme}://{parts.netloc}"
    for path in WELL_KNOWN:
        try:
            return fetch_card(root + path, allow_remote=allow_remote, transport=transport)
        except FetchError as exc:
            if exc.status != 404:
                raise
    raise FetchError(f"{root}: no AgentCard at {' or '.join(WELL_KNOWN)}", status=404)
