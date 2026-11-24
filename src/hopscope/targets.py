"""External A2A targets: configuration and the guard that keeps hopscope off systems you do not own.

By default only local targets pass: loopback addresses, ``localhost`` and the reserved
``.localhost`` / ``.test`` names. Anything else needs ``allow_remote=True``; hopscope cannot check
that you hold written authorisation for it, so the flag exists to make that choice explicit.
No runner drives external targets in v0.1.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit


class TargetRefused(ValueError):
    """The target is not local and remote targets were not explicitly allowed."""


@dataclass(frozen=True, slots=True)
class Target:
    name: str
    card_url: str
    notes: str = ""


def check_target(url: str, *, allow_remote: bool = False) -> str:
    parts = urlsplit(url)
    host = parts.hostname
    if parts.scheme not in ("http", "https") or not host:
        raise TargetRefused(f"target must be an http(s) URL with a host, got {url!r}")
    if allow_remote or host == "localhost" or host.endswith((".localhost", ".test")):
        return host
    try:
        if ipaddress.ip_address(host).is_loopback:
            return host
    except ValueError:
        pass
    raise TargetRefused(f"{host} is not local; pass allow_remote=True only for systems you are authorised to test")


#: Local lab targets. Card paths follow A2A's well-known location; check them against your local build.
KNOWN_LOCAL_TARGETS: tuple[Target, ...] = (
    Target("dvaa-a", "http://127.0.0.1:7020/.well-known/agent-card.json", "Damn Vulnerable AI Agent, run locally"),
    Target("dvaa-b", "http://127.0.0.1:7021/.well-known/agent-card.json", "Damn Vulnerable AI Agent, run locally"),
)
