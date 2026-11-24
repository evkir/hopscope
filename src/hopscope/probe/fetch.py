"""Fetch an AgentCard from a target without leaving the local lab.

The target URL is checked before any request; redirects are refused rather than followed;
environment proxies are ignored so local traffic never leaves through one; the body is capped;
and every URL the card advertises is checked too, because the card is attacker-controlled.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from hopscope.probe.card import CardError, ProbeCard, parse_card
from hopscope.targets import check_target

MAX_CARD_BYTES = 256 * 1024
TIMEOUT_S = 5.0


class FetchError(RuntimeError):
    """The card could not be fetched safely."""


def fetch_json(url: str, *, allow_remote: bool = False, transport: httpx.BaseTransport | None = None) -> Any:
    check_target(url, allow_remote=allow_remote)
    with httpx.Client(transport=transport, timeout=TIMEOUT_S, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", url, headers={"Accept": "application/json"}) as resp:
            if resp.is_redirect:
                raise FetchError(f"{url} redirected to {resp.headers.get('location')!r}; redirects are not followed")
            if resp.status_code != 200:
                raise FetchError(f"{url} returned HTTP {resp.status_code}")
            body = bytearray()
            for chunk in resp.iter_bytes():
                body += chunk
                if len(body) > MAX_CARD_BYTES:
                    raise FetchError(f"{url} card exceeds {MAX_CARD_BYTES} bytes")
    try:
        doc = json.loads(body)
    except ValueError as exc:
        raise CardError(f"{url} did not return JSON: {exc}") from exc
    return doc


def fetch_card(url: str, *, allow_remote: bool = False, transport: httpx.BaseTransport | None = None) -> ProbeCard:
    card = parse_card(fetch_json(url, allow_remote=allow_remote, transport=transport))
    for advertised in card.urls:
        check_target(advertised, allow_remote=allow_remote)
    return card
