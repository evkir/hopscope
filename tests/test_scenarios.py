from __future__ import annotations

import asyncio

import pytest

from hopscope.cli import main
from hopscope.range.demo import run_demo
from hopscope.range.scenarios import SCENARIOS, get_scenario


def test_registry() -> None:
    assert set(SCENARIOS) == {"over-delegation", "compromised-worker", "poisoned-card"}
    assert get_scenario("compromised-worker").compromised == {"worker"}
    with pytest.raises(ValueError, match="unknown scenario"):
        get_scenario("nope")


def test_injected_context_reaches_every_hop_prompt() -> None:
    run = asyncio.run(run_demo(scenario="over-delegation"))
    assert run.result.ok


def test_cli_demo_compromised_a2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--level", "A2", "--scenario", "compromised-worker"]) == 0
    tools = [line for line in capsys.readouterr().out.splitlines() if line.startswith("tool#")]
    assert len(tools) == 3 and all("executed=False" in t for t in tools)


def test_cli_run_level_and_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--n", "3", "--level", "A1", "--scenario", "compromised-worker"]) == 0
    assert "EXR=1.000" in capsys.readouterr().out
    assert main(["run", "--n", "3", "--level", "A1"]) == 0
    assert "EXR=0.000" in capsys.readouterr().out


def test_poisoned_card_summary() -> None:
    from hopscope.range.a2a_bridge.cards import POISONED_SKILL_ID, card_for, card_summary

    assert POISONED_SKILL_ID in card_summary(card_for("planner", poisoned=True))
    assert POISONED_SKILL_ID not in card_summary(card_for("planner"))


def test_poisoned_card_is_what_the_planner_serves() -> None:
    import httpx

    from hopscope.range.a2a_bridge.bridge import build_app
    from hopscope.range.a2a_bridge.cards import POISONED_SKILL_ID, card_for, hop_url
    from hopscope.range.envelope import AgentResult

    class Dummy:
        name = "planner"

        async def handle(self, env):  # type: ignore[no-untyped-def]
            return AgentResult(self.name, True)

    async def go() -> list[str]:
        app = build_app(Dummy(), card_for("planner", poisoned=True))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=hop_url("planner")) as http:
            return [s["id"] for s in (await http.get("/.well-known/agent-card.json")).json()["skills"]]

    assert POISONED_SKILL_ID in asyncio.run(go())


def test_peer_card_reaches_the_delegator_prompt() -> None:
    import json

    from hopscope.harness.llm_client import ScriptedBackend
    from hopscope.range.agent import Agent
    from hopscope.range.envelope import AgentResult, RunTrace, TaskEnvelope
    from hopscope.range.levels import A0
    from hopscope.range.roles import Role
    from hopscope.tools.caps import Mandate

    class Sink:
        name = "planner"

        async def handle(self, env: TaskEnvelope) -> AgentResult:
            return AgentResult(self.name, True)

    llm = ScriptedBackend({"orchestrator": [json.dumps({"instruction": "x", "capabilities": []})]})
    agent = Agent("orchestrator", Role.ORCHESTRATOR, llm, A0(), RunTrace("r", Mandate()), downstream=Sink(), peer_card="CARD")
    asyncio.run(agent.handle(TaskEnvelope("r", 0, "user", "t", Mandate())))
    assert json.loads(llm.transcript[0]["messages"][0]["content"])["peer"] == "CARD"


def test_poisoned_card_excess_is_at_hop_one() -> None:
    from hopscope.meter.exploratory import excess_by_depth

    assert excess_by_depth([asyncio.run(run_demo(scenario="poisoned-card"))]) == {1: 1.0, 2: 0.0, 3: 0.0}
    assert excess_by_depth([asyncio.run(run_demo(scenario="poisoned-card", transport="a2a"))]) == {1: 1.0, 2: 0.0, 3: 0.0}
