"""Wire the four-hop reference chain and run it in-process or over A2A."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from hopscope.harness.llm_client import LLMBackend
from hopscope.range.a2a_bridge.cards import card_for, card_summary
from hopscope.range.agent import Agent
from hopscope.range.envelope import AgentResult, HopRecord, RunTrace, TaskEnvelope
from hopscope.range.levels import Level
from hopscope.range.roles import Role
from hopscope.tools import default_registry
from hopscope.tools.authority import T2
from hopscope.tools.base import ToolEvent
from hopscope.tools.caps import Mandate
from hopscope.tools.gate import Gate
from hopscope.tools.registry import ToolRegistry

DELEGATORS = frozenset({Role.ORCHESTRATOR.value, Role.PLANNER.value, Role.WORKER.value})
ROLES = frozenset(r.value for r in Role)


@dataclass(frozen=True)
class RunResult:
    run_id: str
    level: str
    root: Mandate
    result: AgentResult
    hops: tuple[HopRecord, ...]
    tool_events: tuple[ToolEvent, ...]
    authority: Mandate


def build_chain(
    llm: LLMBackend,
    registry: ToolRegistry,
    level: Level,
    trace: RunTrace,
    gate: Gate | None = None,
    compromised: frozenset[str] = frozenset(),
    poisoned: frozenset[str] = frozenset(),
) -> Agent:
    peer = Agent(Role.EXECUTOR.value, Role.EXECUTOR, llm, level, trace, registry=registry, gate=gate)
    for role in (Role.WORKER, Role.PLANNER, Role.ORCHESTRATOR):
        card = card_for(peer.name, poisoned=peer.name in poisoned)
        peer = Agent(
            role.value, role, llm, level, trace,
            downstream=peer, compromised=role.value in compromised, peer_card=card_summary(card),
        )
    return peer


async def run_chain(
    instruction: str,
    root: Mandate,
    *,
    llm: LLMBackend,
    level: Level,
    registry: ToolRegistry | None = None,
    run_id: str = "run-0",
    context: Sequence[str] = (),
    transport: str = "inproc",
    authority: Mandate | None = None,
    compromised: Iterable[str] = (),
    poisoned: Iterable[str] = (),
) -> RunResult:
    """``authority`` is the executor's C(A), default T2; ``compromised`` names delegating hops;
    ``poisoned`` names hops whose AgentCard carries the poisoned skill."""
    bad, pois = frozenset(compromised), frozenset(poisoned)
    if not bad <= DELEGATORS:
        raise ValueError(f"only delegating hops can be compromised, got {sorted(bad - DELEGATORS)}")
    if not pois <= ROLES:
        raise ValueError(f"unknown hops for poisoned cards: {sorted(pois - ROLES)}")
    registry = registry if registry is not None else default_registry()
    authority = authority if authority is not None else T2
    gate = Gate(root, authority)
    trace = RunTrace(run_id, root)
    head = Role.ORCHESTRATOR.value
    env = TaskEnvelope(run_id, 0, "user", instruction, root, tuple(context), level.root_token(run_id, root, head))
    trace.hops.append(HopRecord(run_id, 0, "user", head, root, root, root))
    if transport == "inproc":
        result = await build_chain(llm, registry, level, trace, gate, bad, pois).handle(env)
    elif transport == "a2a":
        from hopscope.range.a2a_bridge.bridge import a2a_chain

        async with a2a_chain(llm, registry, level, trace, gate, bad, pois) as peer:
            result = await peer.handle(env)
    else:
        raise ValueError(f"unknown transport {transport!r} (expected 'inproc' or 'a2a')")
    return RunResult(run_id, level.name, root, result, tuple(trace.hops), tuple(registry.log), authority)
