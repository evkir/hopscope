from __future__ import annotations

import asyncio
import json
from pathlib import Path

from hopscope.range.demo import run_demo
from hopscope.report.journal import SCHEMA, read_jsonl, run_to_record, write_jsonl


def test_record_shape_and_rulings() -> None:
    rec = run_to_record(asyncio.run(run_demo()), scenario=None)
    assert rec["schema"] == SCHEMA and rec["level"] == "A0" and rec["ok"] is True
    assert [e["ruling"] for e in rec["tool_events"]] == ["in_mandate", "candidate", "candidate"]
    assert [h["excess"] for h in rec["hops"] if h["excess"]] == [["net:post:ops.evil.test", "secrets:get:*"]]


def test_no_canary_in_record() -> None:
    rec = run_to_record(asyncio.run(run_demo()))
    assert "HOPSCOPE-CANARY" not in json.dumps(rec)


def test_jsonl_roundtrip(tmp_path: Path) -> None:
    recs = [run_to_record(asyncio.run(run_demo(run_id=f"demo-{i}")), scenario="over-delegation") for i in range(3)]
    path = tmp_path / "sub" / "runs.jsonl"
    assert write_jsonl(recs, path) == 3
    assert read_jsonl(path) == recs
