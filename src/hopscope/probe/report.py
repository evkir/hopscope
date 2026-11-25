"""Serialise a probe reading as ``hopscope.probe/v1`` JSON (no card text beyond ids and names)."""

from __future__ import annotations

from typing import Any

from hopscope.probe.card import ProbeCard
from hopscope.probe.chain import EdgeReading
from hopscope.probe.dvaa_perms import PermissionReading
from hopscope.probe.grammar import CardReading, read_card

SCHEMA = "hopscope.probe/v1"
CHAIN_SCHEMA = "hopscope.probe.chain/v1"


def _tier(t: int | None) -> str | None:
    return None if t is None else f"T{t}"


def reading_to_dict(card: ProbeCard, reading: CardReading | None = None) -> dict[str, Any]:
    reading = reading if reading is not None else read_card(card)
    return {
        "schema": SCHEMA,
        "card": card.name,
        "card_source": card.source,
        "urls": list(card.urls),
        "extensions": list(card.extensions),
        "tier": _tier(reading.tier),
        "solicits": reading.solicits,
        "implied": list(reading.implied.specs()),
        "solicited": list(reading.solicited.specs()),
        "out_of_vocabulary": sorted({o for s in reading.skills for o in s.out_of_vocabulary}),
        "skills": [
            {
                "id": s.skill_id,
                "tier": _tier(s.tier),
                "solicits": s.solicits,
                "implied": list(s.implied.specs()),
                "solicited": list(s.solicited.specs()),
                "out_of_vocabulary": list(s.out_of_vocabulary),
            }
            for s in reading.skills
        ],
    }


def _safe(text: str) -> str:
    """Card text is attacker-controlled: never let it reach a terminal with control sequences."""
    return "".join(c if c.isprintable() else "?" for c in text)


def format_report(d: dict[str, Any]) -> str:
    def join(xs: list[str]) -> str:
        return ", ".join(_safe(x) for x in xs) or "-"

    lines = [
        f"card {_safe(d['card'])} [{_safe(d['card_source'])}]  tier {d['tier'] or '-'}  solicits {'YES' if d['solicits'] else 'no'}",
        f"  urls:      {join(d['urls'])}",
        f"  implied:   {join(d['implied'])}",
        f"  solicited: {join(d['solicited'])}",
        f"  oov:       {join(d['out_of_vocabulary'])}",
    ]
    for s in d["skills"]:
        flag = "  SOLICITS" if s["solicits"] else ""
        lines.append(f"  skill {_safe(s['id']):<24} tier {s['tier'] or '-'}{flag}")
    return "\n".join(lines)


def _side(p: PermissionReading) -> dict[str, Any]:
    return {
        "labels": list(p.labels),
        "caps": list(p.mandate.specs()),
        "tier": _tier(p.tier),
        "out_of_vocabulary": list(p.oov),
        "unmapped": list(p.unmapped),
    }


def edge_to_dict(edge: EdgeReading, *, target: str) -> dict[str, Any]:
    """``hopscope.probe.chain/v1``: one recorded hop; context only as length + sha256."""
    return {
        "schema": CHAIN_SCHEMA,
        "target": target,
        "hop": edge.hop,
        "task_id": edge.task_id,
        "held": _side(edge.held),
        "granted": _side(edge.granted),
        "excess": sorted(str(c) for c in edge.excess),
        "oov_added": list(edge.oov_added),
        "flags": {
            "origin_rewritten": edge.origin_rewritten,
            "context_appended": edge.context_appended,
            "context_rewritten": edge.context_rewritten,
            "hidden_fields": list(edge.hidden_fields),
        },
        "context": {
            "in": {"length": edge.context_in.length, "sha256": edge.context_in.sha256},
            "out": {"length": edge.context_out.length, "sha256": edge.context_out.sha256},
        },
        "escalated": edge.escalated,
        "poisoned": edge.poisoned,
    }


def format_edge(d: dict[str, Any]) -> str:
    """Labels, task ids and field names come from the target: sanitised like card text."""

    def join(xs: list[str]) -> str:
        return ", ".join(_safe(x) for x in xs) or "-"

    def side(s: dict[str, Any]) -> str:
        oov = f"  oov {join(s['out_of_vocabulary'])}" if s["out_of_vocabulary"] else ""
        unm = f"  unmapped {join(s['unmapped'])}" if s["unmapped"] else ""
        return f"{s['tier'] or '-':<3} {join(s['caps'])}  [{join(s['labels'])}]{oov}{unm}"

    f, ctx = d["flags"], d["context"]
    flags = [n for n in ("origin_rewritten", "context_appended", "context_rewritten") if f[n]]
    if f["context_appended"] or f["context_rewritten"]:
        flags.append(f"context {ctx['in']['length']}->{ctx['out']['length']} chars")
    if f["hidden_fields"]:
        flags.append(f"hidden {join(f['hidden_fields'])}")
    excess = d["excess"] + [f"oov:{o}" for o in d["oov_added"]]
    status = "POISONED" if d["poisoned"] else "clean"
    return "\n".join(
        [
            f"edge {_safe(d['hop'])} task {_safe(d['task_id'])} [{_safe(d['target'])}]  {status}",
            f"  held:     {side(d['held'])}",
            f"  granted:  {side(d['granted'])}",
            f"  EXCESS:   {join(excess)}",
            f"  flags:    {join(flags)}",
        ]
    )
