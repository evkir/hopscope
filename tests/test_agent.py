from __future__ import annotations

import asyncio
import json

import pytest

from hopscope.harness.llm_client import ScriptedBackend
from hopscope.range.agent import Agent
from hopscope.range.envelope import AgentResult, RunTrace, TaskEnvelope
from hopscope.range.levels import L0
from hopscope.range.roles import Role
from hopscope.tools import default_registry
from hopscope.tools.caps import Mandate

ROOT = Mandate.of("fs:read:/workspace/*")


class Sink:
    name = "sink"

    def __init__(self) -> None:
        self.got: list[TaskEnvelope] = []

    async def handle(self, env: TaskEnvelope) -> AgentResult:
        self.got.append(env)
        return AgentResult(self.name, ok=True)


def env() -> TaskEnvelope:
    return TaskEnvelope("r", 1, "orchestrator", "task", ROOT)


def test_constructor_validates_wiring() -> None:
    llm, trace = ScriptedBackend(), RunTrace("r", ROOT)
    with pytest.raises(ValueError):
        Agent("e", Role.EXECUTOR, llm, L0(), trace)
    with pytest.raises(ValueError):
        Agent("p", Role.PLANNER, llm, L0(), trace, registry=default_registry())


def test_planner_fans_out_and_records_hops() -> None:
    steps = {"steps": [
        {"instruction": "read", "capabilities": ["fs:read:/workspace/*"]},
        {"instruction": "steal", "capabilities": ["secrets:get:*"]},
    ]}
    sink, trace = Sink(), RunTrace("r", ROOT)
    agent = Agent("planner", Role.PLANNER, ScriptedBackend({"planner": [json.dumps(steps)]}), L0(), trace, downstream=sink)
    res = asyncio.run(agent.handle(env()))
    assert res.ok and len(res.children) == 2
    assert [e.hop for e in sink.got] == [2, 2] and sink.got[1].mandate == Mandate.of("secrets:get:*")
    assert [bool(h.inflation) for h in trace.hops] == [False, True]
    assert {h.receiver for h in trace.hops} == {"sink"}


@pytest.mark.parametrize("reply", ["not json", '{"instruction": "", "capabilities": []}', '{"instruction": "x", "capabilities": ["bogus:a:b"]}'])
def test_bad_delegation_does_not_call_downstream(reply: str) -> None:
    sink = Sink()
    agent = Agent("worker", Role.WORKER, ScriptedBackend({"worker": [reply]}), L0(), RunTrace("r", ROOT), downstream=sink)
    res = asyncio.run(agent.handle(env()))
    assert not res.ok and res.errors and not sink.got


def test_executor_dispatches_and_reports_bad_calls() -> None:
    reply = {"tool_calls": [
        {"tool": "fs", "action": "read", "args": {"path": "/workspace/README.md"}},
        {"tool": "nope", "action": "x", "args": {}},
    ]}
    reg = default_registry()
    agent = Agent("executor", Role.EXECUTOR, ScriptedBackend({"executor": [json.dumps(reply)]}), L0(), RunTrace("r", ROOT), registry=reg)
    res = asyncio.run(agent.handle(env()))
    assert not res.ok and len(res.outputs) == 1 and res.outputs[0]["executed"]
    assert len(reg.log) == 1 and reg.log[0].call.caller == "executor"
