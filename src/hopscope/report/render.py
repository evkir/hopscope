"""Self-contained HTML report: matrix, per-cell exploratory metrics, one trace per cell. No script, no timestamp."""

from __future__ import annotations

import html
from collections.abc import Sequence

from hopscope.meter.exploratory import format_exploratory
from hopscope.meter.matrix import Cell, CellRuns
from hopscope.range.demo import summarize

CSS = (
    "body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1b1f24}"
    "table{border-collapse:collapse}td,th{border:1px solid #d0d7de;padding:.3rem .6rem}"
    "pre{background:#f6f8fa;padding:.8rem;overflow-x:auto}"
)


def _v(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def render_html(cells: Sequence[Cell], collected: Sequence[CellRuns], *, version: str) -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(c.scenario)}</td><td>{e(c.level)}</td><td>{_v(c.metrics.cir)}</td>"
        f"<td>{_v(c.metrics.esr)}</td><td>{_v(c.metrics.exr)}</td></tr>"
        for c in cells
    )
    sections = "".join(
        f"<section><h3>{e(cr.scenario)} · {e(cr.level)}</h3>"
        f"<p>{e(format_exploratory(list(cr.runs)))}</p>"
        f"<pre>{e(chr(10).join(summarize(cr.runs[0])) if cr.runs else '(no runs)')}</pre></section>"
        for cr in collected
    )
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>hopscope {e(version)} report</title><style>{CSS}</style></head><body>"
        f"<h1>hopscope {e(version)}</h1>"
        "<p>Deterministic demo: every cell replays the same scripted attack, so the matrix shows what each "
        "attenuation level stops, not how often a model attacks.</p>"
        "<p><strong>CIR is not MIR.</strong> CIR counts runs with a gate ruling CANDIDATE (PPD D7(i)-(ii)); "
        "EXR counts runs in which such a call executed; the λ metrics are exploratory and not pre-registered.</p>"
        "<table><thead><tr><th>scenario</th><th>level</th><th>CIR</th><th>ESR</th><th>EXR</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>{sections}</body></html>\n"
    )
