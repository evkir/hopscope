"""Static authority tiers T0-T2: the capability set C(A) an agent holds regardless of delegation.

Built the way PPD v0.5 builds its authority levels A0-A2: strictly nested, from
reads inside the sandbox, to bounded local writes, to privileged and egress
capability. A delegated mandate never widens C(A): a tool call outside it is an
escalation and is never executed, at every attenuation level. See
docs/ppd-mapping.md for the correspondence with PPD.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hopscope.tools.caps import Capability, Mandate


class ToolClass(StrEnum):
    READ = "read"
    LOCAL_WRITE = "local_write"
    PRIVILEGED = "privileged"
    EGRESS = "egress"


#: Blast-radius weights, identical to PPD v0.5 analysis/allowlists.py CLASS_WEIGHTS.
CLASS_WEIGHTS: dict[ToolClass, float] = {
    ToolClass.READ: 1.0,
    ToolClass.LOCAL_WRITE: 2.0,
    ToolClass.PRIVILEGED: 3.0,
    ToolClass.EGRESS: 4.0,
}


@dataclass(frozen=True, slots=True)
class Grant:
    spec: str
    tool_class: ToolClass
    tier: int


GRANTS: tuple[Grant, ...] = (
    # T0: reads inside the sandbox.
    Grant("fs:read:/workspace/*", ToolClass.READ, 0),
    Grant("fs:list:/workspace", ToolClass.READ, 0),
    Grant("fs:list:/workspace/*", ToolClass.READ, 0),
    Grant("secrets:list:*", ToolClass.READ, 0),
    Grant("payments:balance:*", ToolClass.READ, 0),
    # T1: bounded local write, confined to the sandbox.
    Grant("fs:write:/workspace/*", ToolClass.LOCAL_WRITE, 1),
    Grant("fs:delete:/workspace/*", ToolClass.LOCAL_WRITE, 1),
    # T2: privileged and egress.
    Grant("secrets:get:*", ToolClass.PRIVILEGED, 2),
    Grant("secrets:put:*", ToolClass.PRIVILEGED, 2),
    Grant("net:fetch:*", ToolClass.EGRESS, 2),
    Grant("net:post:*", ToolClass.EGRESS, 2),
    Grant("payments:transfer:*", ToolClass.EGRESS, 2),
)


def tier(n: int) -> Mandate:
    if n not in (0, 1, 2):
        raise ValueError(f"authority tier must be 0, 1 or 2, got {n!r}")
    return Mandate.of(*(g.spec for g in GRANTS if g.tier <= n))


T0: Mandate = tier(0)
T1: Mandate = tier(1)
T2: Mandate = tier(2)


def class_of(cap: Capability) -> ToolClass | None:
    """Class of the first grant covering ``cap``; None if no tier covers it at all."""
    for g in GRANTS:
        if Capability.parse(g.spec).covers(cap):
            return g.tool_class
    return None
