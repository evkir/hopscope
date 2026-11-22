"""Wire the four-hop reference chain and run it in-process or over A2A."""

from __future__ import annotations

from collections.abc import Sequence
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
    llm: LLMBackend, registry: ToolRegistry, level: Level, trace: RunTrace, gate: Gate | None = None
) -> Agent:
    executor = Agent(Role.EXECUTOR.value, Role.EXECUTOR, llm, level, trace, registry=registry, gate=gate)
    worker = Agent(Role.WORKER.value, Role.WORKER, llm, level, trace, downstream=executor)
    planner = Agent(Role.PLANNER.value, Role.PLANNER, llm, level, trace, downstream=worker)
    return Agent(Role.ORCHESTRATOR.value, Role.ORCHESTRATOR, llm, level, trace, downstream=planner)


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
) -> RunResult:
    """``authority`` is the executor's C(A); default T2."""
    registry = registry if registry is not None else default_registry()
    authority = authority if authority is not None else T2
    gate = Gate(root, authority)
    trace = RunTrace(run_id, root)
    env = TaskEnvelope(run_id, 0, "user", instruction, root, tuple(context))
    if transport == "inproc":
        head = build_chain(llm, registry, level, trace, gate)
        trace.hops.append(HopRecord(run_id, 0, "user", head.name, root, root, root))
        result = await head.handle(env)
    elif transport == "a2a":
        from hopscope.range.a2a_bridge.bridge import a2a_chain

        async with a2a_chain(llm, registry, level, trace, gate) as peer:
            trace.hops.append(HopRecord(run_id, 0, "user", peer.name, root, root, root))
            result = await peer.handle(env)
    else:
        raise ValueError(f"unknown transport {transport!r} (expected 'inproc' or 'a2a')")
    return RunResult(run_id, level.name, root, result, tuple(trace.hops), tuple(registry.log), authority)
