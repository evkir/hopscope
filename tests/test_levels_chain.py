from __future__ import annotations

import asyncio

import pytest

from hopscope.harness.llm_client import ScriptedBackend
from hopscope.range.chain import RunResult, run_chain
from hopscope.range.demo import DEMO_INSTRUCTION, DEMO_ROOT, DEMO_SCRIPT
from hopscope.range.levels import A0, A1, A2, Level
from hopscope.tools.caps import Mandate
from hopscope.tools.gate import Ruling

C, IN = Ruling.CANDIDATE, Ruling.IN_MANDATE


def run(level: Level, *, compromised: tuple[str, ...] = (), transport: str = "inproc") -> RunResult:
    return asyncio.run(run_chain(
        DEMO_INSTRUCTION, Mandate.of(*DEMO_ROOT), llm=ScriptedBackend(DEMO_SCRIPT), level=level,
        compromised=compromised, transport=transport,
    ))


def executed(r: RunResult) -> list[bool]:
    return [e.executed for e in r.tool_events]


@pytest.mark.parametrize(("level", "want"), [(A0(), [True, True, True]), (A1(), [True, False, False]), (A2(), [True, False, False])])
def test_honest_chain(level: Level, want: list[bool]) -> None:
    r = run(level)
    assert executed(r) == want and [e.ruling for e in r.tool_events] == [IN, C, C]


@pytest.mark.parametrize("level", [A1(), A2()])
def test_attenuation_leaves_no_hop_excess(level: Level) -> None:
    assert not any(h.excess for h in run(level).hops)


@pytest.mark.parametrize("transport", ["inproc", "a2a"])
@pytest.mark.parametrize(("level", "want"), [(A1(), [True, True, True]), (A2(), [False, False, False])])
def test_compromised_worker(level: Level, want: list[bool], transport: str) -> None:
    r = run(level, compromised=("worker",), transport=transport)
    assert executed(r) == want
    assert any(h.sender == "worker" and h.excess for h in r.hops)


@pytest.mark.parametrize("bad", [("executor",), ("nobody",)])
def test_only_delegators_can_be_compromised(bad: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="delegating"):
        run(A0(), compromised=bad)
