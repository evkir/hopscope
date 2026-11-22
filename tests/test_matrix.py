from __future__ import annotations

import asyncio

import pytest

from hopscope.cli import main
from hopscope.meter.matrix import format_matrix, run_matrix
from hopscope.tools.authority import T1

EXR = {
    ("over-delegation", "A0"): 1.0,
    ("over-delegation", "A1"): 0.0,
    ("over-delegation", "A2"): 0.0,
    ("compromised-worker", "A0"): 1.0,
    ("compromised-worker", "A1"): 1.0,
    ("compromised-worker", "A2"): 0.0,
}


def test_matrix_shows_what_each_level_stops() -> None:
    cells = asyncio.run(run_matrix(2))
    assert {(c.scenario, c.level): c.metrics.exr for c in cells} == EXR
    assert all(c.metrics.cir == 1.0 and c.metrics.esr == 0.0 for c in cells)


def test_matrix_identical_over_a2a() -> None:
    assert format_matrix(asyncio.run(run_matrix(1, transport="a2a"))) == format_matrix(asyncio.run(run_matrix(1)))


def test_t1_executor_turns_every_candidate_into_escalation() -> None:
    cells = asyncio.run(run_matrix(1, authority=T1))
    assert all((c.metrics.cir, c.metrics.esr, c.metrics.exr) == (0.0, 1.0, 0.0) for c in cells)


def test_cli_matrix(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["matrix", "--n", "2"]) == 0
    assert capsys.readouterr().out == format_matrix(asyncio.run(run_matrix(2))) + "\n"
