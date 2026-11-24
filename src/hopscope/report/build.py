"""Build all reports for the full scenario x level matrix."""

from __future__ import annotations

import json
from pathlib import Path

from hopscope import __version__
from hopscope.meter.matrix import cells_from, collect
from hopscope.report.journal import run_to_record, write_jsonl
from hopscope.report.render import render_html
from hopscope.report.sarif import to_sarif
from hopscope.tools.caps import Mandate


async def build_report(
    out: Path, n: int = 10, *, transport: str = "inproc", authority: Mandate | None = None
) -> dict[str, Path]:
    collected = await collect(n, transport=transport, authority=authority)
    out.mkdir(parents=True, exist_ok=True)
    paths = {"jsonl": out / "runs.jsonl", "sarif": out / "hopscope.sarif", "html": out / "report.html"}
    write_jsonl((run_to_record(r, scenario=c.scenario, transport=transport) for c in collected for r in c.runs),
                paths["jsonl"])
    paths["sarif"].write_text(json.dumps(to_sarif(collected, version=__version__), indent=2, sort_keys=True) + "\n",
                              encoding="utf-8")
    paths["html"].write_text(render_html(cells_from(collected), collected, version=__version__), encoding="utf-8")
    return paths
