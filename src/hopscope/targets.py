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
    #: DVAA agent id: the card is synthesized from the dashboard's /agents API (no published card).
    dvaa_agent: str = ""


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


#: Local lab targets. DVAA 0.9.2's A2A agents (:7020, :7021) publish no AgentCard (404 on both
#: well-known paths), so their card is read from the dashboard API and marked as synthesized.
KNOWN_LOCAL_TARGETS: tuple[Target, ...] = (
    Target("dvaa-a", "http://127.0.0.1:9000/agents", "DVAA Orchestrator (:7020), run locally", "orchestrator"),
    Target("dvaa-b", "http://127.0.0.1:9000/agents", "DVAA Worker Agent (:7021), run locally", "worker-1"),
)
