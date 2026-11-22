"""Wire the four-hop reference chain and run it in-process or over A2A."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from hopscope.harness.llm_client import LLMBackend
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
) -> Agent:
    executor = Agent(Role.EXECUTOR.value, Role.EXECUTOR, llm, level, trace, registry=registry, gate=gate)
    peer: Agent = executor
    for role in (Role.WORKER, Role.PLANNER, Role.ORCHESTRATOR):
        peer = Agent(role.value, role, llm, level, trace, downstream=peer, compromised=role.value in compromised)
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
) -> RunResult:
    """``authority`` is the executor's C(A), default T2; ``compromised`` names delegating hops."""
    bad = frozenset(compromised)
    if not bad <= DELEGATORS:
        raise ValueError(f"only delegating hops can be compromised, got {sorted(bad - DELEGATORS)}")
    registry = registry if registry is not None else default_registry()
    authority = authority if authority is not None else T2
    gate = Gate(root, authority)
    trace = RunTrace(run_id, root)
    head = Role.ORCHESTRATOR.value
    env = TaskEnvelope(run_id, 0, "user", instruction, root, tuple(context), level.root_token(run_id, root, head))
    trace.hops.append(HopRecord(run_id, 0, "user", head, root, root, root))
    if transport == "inproc":
        result = await build_chain(llm, registry, level, trace, gate, bad).handle(env)
    elif transport == "a2a":
        from hopscope.range.a2a_bridge.bridge import a2a_chain

        async with a2a_chain(llm, registry, level, trace, gate, bad) as peer:
            result = await peer.handle(env)
    else:
        raise ValueError(f"unknown transport {transport!r} (expected 'inproc' or 'a2a')")
    return RunResult(run_id, level.name, root, result, tuple(trace.hops), tuple(registry.log), authority)
