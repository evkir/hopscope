from __future__ import annotations

import asyncio

import pytest

from hopscope.cli import main
from hopscope.range.demo import run_demo
from hopscope.range.scenarios import SCENARIOS, get_scenario


def test_registry() -> None:
    assert set(SCENARIOS) == {"over-delegation", "compromised-worker"}
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
