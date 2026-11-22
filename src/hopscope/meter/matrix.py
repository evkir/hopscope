"""Scenario x attenuation-level matrix of CIR / ESR / EXR over the deterministic demo."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from hopscope.meter.metrics import EnsembleMetrics, ensemble_metrics, run_metrics
from hopscope.range.demo import run_demo_ensemble
from hopscope.range.scenarios import SCENARIOS
from hopscope.tools.caps import Mandate

LEVEL_ORDER: tuple[str, ...] = ("A0", "A1", "A2")


@dataclass(frozen=True, slots=True)
class Cell:
    scenario: str
    level: str
    metrics: EnsembleMetrics


async def run_matrix(
    n: int,
    *,
    transport: str = "inproc",
    authority: Mandate | None = None,
    levels: Sequence[str] = LEVEL_ORDER,
    scenarios: Sequence[str] | None = None,
) -> list[Cell]:
    cells: list[Cell] = []
    for sc in scenarios if scenarios is not None else tuple(SCENARIOS):
        for lv in levels:
            runs = await run_demo_ensemble(n, transport, authority=authority, level=lv, scenario=sc)
            cells.append(Cell(sc, lv, ensemble_metrics([run_metrics(r) for r in runs])))
    return cells


def format_matrix(cells: Sequence[Cell]) -> str:
    def v(x: float | None) -> str:
        return "  n/a" if x is None else f"{x:5.2f}"

    lines = [f"{'scenario':<20} {'level':<5} {'CIR':>5} {'ESR':>5} {'EXR':>5}"]
    for c in cells:
        m = c.metrics
        lines.append(f"{c.scenario:<20} {c.level:<5} {v(m.cir)} {v(m.esr)} {v(m.exr)}")
    return "\n".join(lines)
