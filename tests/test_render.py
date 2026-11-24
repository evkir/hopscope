from __future__ import annotations

import asyncio

from hopscope.meter.matrix import Cell, CellRuns, cells_from, collect
from hopscope.meter.metrics import ensemble_metrics
from hopscope.report.render import render_html


def test_report_has_matrix_and_disclaimer() -> None:
    collected = asyncio.run(collect(1))
    out = render_html(cells_from(collected), collected, version="0.1.0")
    assert out.count("<tr>") == 10 and "CIR is not MIR" in out and "hopscope 0.1.0" in out
    assert "tool#1 executor secrets:get:api_key executed=True CANDIDATE" in out
    assert out == render_html(cells_from(collected), collected, version="0.1.0")


def test_everything_is_escaped() -> None:
    evil = "<script>alert(1)</script>"
    out = render_html([Cell(evil, "A0", ensemble_metrics([]))], [CellRuns(evil, "A0", ())], version=evil)
    assert "<script>" not in out and "&lt;script&gt;" in out and "n/a" in out
