from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack

import httpx

from hopscope.range.a2a_bridge.bridge import A2APeer, build_app, expose
from hopscope.range.a2a_bridge.cards import card_for, hop_url
from hopscope.range.envelope import AgentResult, TaskEnvelope
from hopscope.tools.caps import Mandate

ENV = TaskEnvelope("r", 3, "worker", "run tools", Mandate.of("secrets:get:*"), ("c",))


class Recorder:
    name = "executor"

    def __init__(self) -> None:
        self.got: list[TaskEnvelope] = []

    async def handle(self, env: TaskEnvelope) -> AgentResult:
        self.got.append(env)
        return AgentResult(self.name, True, outputs=[{"seq": 0, "result": "HOPSCOPE-CANARY-api_key"}])


def test_peer_roundtrip_over_jsonrpc() -> None:
    async def go() -> tuple[AgentResult, list[TaskEnvelope]]:
        rec = Recorder()
        async with AsyncExitStack() as stack:
            peer = await expose(stack, rec)
            res = await peer.handle(ENV)
        return res, rec.got

    res, got = asyncio.run(go())
    assert got == [ENV]
    assert res.ok and res.outputs[0]["result"] == "HOPSCOPE-CANARY-api_key"


def test_agent_card_served() -> None:
    async def go() -> int:
        app = build_app(Recorder(), card_for("executor"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=hop_url("executor")) as http:
            r = await http.get("/.well-known/agent-card.json")
            assert r.json()["name"] == "executor"
            return r.status_code

    assert asyncio.run(go()) == 200


def test_peer_name_matches_card() -> None:
    async def go() -> str:
        async with httpx.AsyncClient() as http:
            return A2APeer(card_for("planner"), http).name

    assert asyncio.run(go()) == "planner"
