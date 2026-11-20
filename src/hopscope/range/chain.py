"""Wire the four-hop reference chain and run it in-process."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from hopscope.harness.llm_client import LLMBackend
from hopscope.range.agent import Agent
from hopscope.range.envelope import AgentResult, HopRecord, RunTrace, TaskEnvelope
from hopscope.range.levels import Level
from hopscope.range.roles import Role
from hopscope.tools import default_registry
from hopscope.tools.base import ToolEvent
from hopscope.tools.caps import Mandate
from hopscope.tools.registry import ToolRegistry


@dataclass(frozen=True)
class RunResult:
    run_id: str
    level: str
    root: Mandate
    result: AgentResult
    hops: tuple[HopRecord, ...]
    tool_events: tuple[ToolEvent, ...]


def build_chain(llm: LLMBackend, registry: ToolRegistry, level: Level, trace: RunTrace) -> Agent:
    executor = Agent(Role.EXECUTOR.value, Role.EXECUTOR, llm, level, trace, registry=registry)
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
) -> RunResult:
    registry = registry if registry is not None else default_registry()
    trace = RunTrace(run_id, root)
    head = build_chain(llm, registry, level, trace)
    trace.hops.append(HopRecord(run_id, 0, "user", head.name, root, root, root))
    result = await head.handle(TaskEnvelope(run_id, 0, "user", instruction, root, tuple(context)))
    return RunResult(run_id, level.name, root, result, tuple(trace.hops), tuple(registry.log))
