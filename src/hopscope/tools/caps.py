"""Capability labels for simulated tools.

A capability is ``domain:action:resource``. ``action`` and ``resource`` are
fnmatch-style patterns (``*`` also matches ``/``). A mandate is the set of
capabilities a principal holds at a given delegation hop.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatchcase


class Domain(StrEnum):
    FS = "fs"
    SECRETS = "secrets"
    PAYMENTS = "payments"
    NET = "net"


@dataclass(frozen=True, slots=True, order=True)
class Capability:
    domain: Domain
    action: str
    resource: str = "*"

    def __post_init__(self) -> None:
        if not isinstance(self.domain, Domain):
            object.__setattr__(self, "domain", Domain(self.domain))
        if not self.action or not self.resource:
            raise ValueError("capability action and resource must be non-empty")

    @classmethod
    def parse(cls, spec: str) -> Capability:
        parts = spec.split(":", 2)
        if len(parts) != 3:
            raise ValueError(f"capability must be domain:action:resource, got {spec!r}")
        return cls(Domain(parts[0]), parts[1], parts[2])

    def covers(self, other: Capability) -> bool:
        return (
            self.domain == other.domain
            and fnmatchcase(other.action, self.action)
            and fnmatchcase(other.resource, self.resource)
        )

    def __str__(self) -> str:
        return f"{self.domain}:{self.action}:{self.resource}"


@dataclass(frozen=True, slots=True)
class Mandate:
    caps: frozenset[Capability] = frozenset()

    @classmethod
    def of(cls, *specs: str) -> Mandate:
        return cls(frozenset(Capability.parse(s) for s in specs))

    def allows(self, required: Capability) -> bool:
        return any(c.covers(required) for c in self.caps)

    def excess(self, requested: Mandate) -> frozenset[Capability]:
        """Capabilities in ``requested`` this mandate does not cover (the inflation set)."""
        return frozenset(c for c in requested.caps if not self.allows(c))

    def covers(self, requested: Mandate) -> bool:
        return not self.excess(requested)

    def specs(self) -> tuple[str, ...]:
        return tuple(str(c) for c in sorted(self.caps))

    def __str__(self) -> str:
        return ", ".join(self.specs())
