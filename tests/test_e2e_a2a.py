from __future__ import annotations

import asyncio

import pytest
from test_e2e_demo import GOLDEN

from hopscope.cli import main
from hopscope.range.demo import run_demo, summarize


def test_golden_trace_identical_over_a2a() -> None:
    run = asyncio.run(run_demo("a2a"))
    assert run.result.ok and summarize(run) == GOLDEN


def test_result_tree_survives_the_wire() -> None:
    run = asyncio.run(run_demo("a2a"))
    planner = run.result.children[0]
    assert [c.agent for c in planner.children] == ["worker", "worker"]
    leaf = planner.children[1].children[0]
    assert leaf.agent == "executor" and leaf.outputs[0]["result"] == "HOPSCOPE-CANARY-api_key"


def test_unknown_transport() -> None:
    with pytest.raises(ValueError, match="unknown transport"):
        asyncio.run(run_demo("smoke-signals"))


def test_cli_demo_a2a(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--transport", "a2a"]) == 0
    assert capsys.readouterr().out.splitlines() == GOLDEN
