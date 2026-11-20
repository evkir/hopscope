"""Data passed between hops and the per-run delegation trace."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hopscope.tools.caps import Capability, Mandate


@dataclass(frozen=True, slots=True)
class TaskEnvelope:
    run_id: str
    hop: int
    sender: str
    instruction: str
    mandate: Mandate
    context: tuple[str, ...] = ()

    def child(self, sender: str, instruction: str, mandate: Mandate) -> TaskEnvelope:
        return TaskEnvelope(self.run_id, self.hop + 1, sender, instruction, mandate, self.context)


@dataclass(frozen=True, slots=True)
class HopRecord:
    """One delegation edge. ``hop`` is the receiver's hop index."""

    run_id: str
    hop: int
    sender: str
    receiver: str
    held: Mandate
    requested: Mandate
    granted: Mandate

    @property
    def inflation(self) -> frozenset[Capability]:
        return self.held.excess(self.granted)


@dataclass
class AgentResult:
    agent: str
    ok: bool
    outputs: list[Any] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    children: list[AgentResult] = field(default_factory=list)


@dataclass
class RunTrace:
    run_id: str
    root: Mandate
    hops: list[HopRecord] = field(default_factory=list)
