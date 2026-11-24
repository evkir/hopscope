"""JSONL journal of runs: one self-describing record per run.

Tool arguments and results are not recorded, so canary values never reach a report.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from hopscope.range.chain import RunResult

SCHEMA = "hopscope.run/v1"


def run_to_record(run: RunResult, *, scenario: str | None = None, transport: str = "inproc") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "run_id": run.run_id,
        "scenario": scenario,
        "level": run.level,
        "transport": transport,
        "ok": run.result.ok,
        "root": list(run.root.specs()),
        "authority": list(run.authority.specs()),
        "hops": [
            {
                "hop": h.hop,
                "sender": h.sender,
                "receiver": h.receiver,
                "held": list(h.held.specs()),
                "requested": list(h.requested.specs()),
                "granted": list(h.granted.specs()),
                "excess": sorted(str(c) for c in h.excess),
            }
            for h in run.hops
        ],
        "tool_events": [
            {
                "seq": e.seq,
                "caller": e.call.caller,
                "tool": e.call.tool,
                "action": e.call.action,
                "required": str(e.required),
                "ruling": e.ruling.value if e.ruling is not None else None,
                "authorized": e.authorized,
                "executed": e.executed,
                "error": e.error,
            }
            for e in run.tool_events
        ],
    }


def write_jsonl(records: Iterable[Mapping[str, Any]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
