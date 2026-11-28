"""SARIF 2.1.0 findings. Locations are logical (scenario/level/run/agent): the range is not source code."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from hopscope.meter.matrix import CellRuns
from hopscope.probe.chain import EdgeReading
from hopscope.tools.gate import Ruling

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

RULES: tuple[dict[str, Any], ...] = (
    {
        "id": "HSC001",
        "name": "ExecutedCandidate",
        "shortDescription": {"text": "Out-of-mandate call executed inside the executor's capability set"},
        "defaultConfiguration": {"level": "error"},
    },
    {
        "id": "HSC002",
        "name": "BlockedCandidate",
        "shortDescription": {"text": "Out-of-mandate call blocked by attenuation"},
        "defaultConfiguration": {"level": "warning"},
    },
    {
        "id": "HSC003",
        "name": "Escalation",
        "shortDescription": {"text": "Call outside the executor's capability set (escalation, never executed)"},
        "defaultConfiguration": {"level": "note"},
    },
    {
        "id": "HSC004",
        "name": "DelegationExcess",
        "shortDescription": {"text": "Delegation granted beyond what the sender held"},
        "defaultConfiguration": {"level": "warning"},
    },
    {
        "id": "HSC005",
        "name": "DelegationTampering",
        "shortDescription": {"text": "Delegation edge tampered without privilege gain"},
        "defaultConfiguration": {"level": "note"},
    },
)
LEVELS: dict[str, str] = {r["id"]: r["defaultConfiguration"]["level"] for r in RULES}


def _result(rule: str, text: str, cell: CellRuns, run_id: str, agent: str, extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "ruleId": rule,
        "level": LEVELS[rule],
        "message": {"text": text},
        "locations": [{
            "logicalLocations": [{
                "name": agent,
                "fullyQualifiedName": f"{cell.scenario}/{cell.level}/{run_id}/{agent}",
                "kind": "module",
            }]
        }],
        "properties": {"scenario": cell.scenario, "level": cell.level, "run_id": run_id, **extra},
    }


def to_sarif(collected: Sequence[CellRuns], *, version: str) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for cell in collected:
        for run in cell.runs:
            for e in run.tool_events:
                if e.ruling is Ruling.CANDIDATE:
                    rule = "HSC001" if e.executed else "HSC002"
                elif e.ruling is Ruling.ESCALATION:
                    rule = "HSC003"
                else:
                    continue
                state = "executed" if e.executed else "blocked"
                results.append(_result(rule, f"{e.call.caller} invoked {e.required} ({state})", cell, run.run_id,
                                       e.call.caller, {"seq": e.seq}))
            for h in run.hops:
                if h.excess:
                    caps = ", ".join(sorted(str(c) for c in h.excess))
                    results.append(_result("HSC004", f"{h.sender} delegated {caps} to {h.receiver} beyond what it held",
                                           cell, run.run_id, h.sender, {"hop": h.hop}))
    return _document(results, version)


def _document(results: list[dict[str, Any]], version: str) -> dict[str, Any]:
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "hopscope",
                "version": version,
                "informationUri": "https://github.com/evkir/hopscope",
                "rules": list(RULES),
            }},
            "results": results,
        }],
    }


def _printable(s: str) -> str:
    return "".join(c if c.isprintable() else "?" for c in s)


def _tier(t: int | None) -> str | None:
    return None if t is None else f"T{t}"


def edges_to_sarif(edges: Sequence[EdgeReading], *, version: str, target: str) -> dict[str, Any]:
    """HSC004 for recorded hops of an external target: same rule and orientation as the range."""
    results: list[dict[str, Any]] = []
    for e in edges:
        if not e.escalated:
            continue
        granted = sorted(str(c) for c in e.excess) + [f"oov:{o}" for o in e.oov_added]
        hop, task = _printable(e.hop), _printable(e.task_id)
        results.append({
            "ruleId": "HSC004",
            "level": LEVELS["HSC004"],
            "message": {"text": f"{hop} delegated {', '.join(granted)} beyond what it held (task {task})"},
            "locations": [{
                "logicalLocations": [{
                    "name": hop,
                    "fullyQualifiedName": f"{target}/{hop}/{task}",
                    "kind": "module",
                }]
            }],
            "properties": {
                "target": target,
                "hop": hop,
                "task_id": task,
                "held_tier": _tier(e.held.tier),
                "granted_tier": _tier(e.granted.tier),
                "excess": granted,
                "origin_rewritten": e.origin_rewritten,
                "context_appended": e.context_appended,
                "context_rewritten": e.context_rewritten,
                "hidden_fields": [_printable(k) for k in e.hidden_fields],
            },
        })
    return _document(results, version)
