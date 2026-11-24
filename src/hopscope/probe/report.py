"""Serialise a probe reading as ``hopscope.probe/v1`` JSON (no card text beyond ids and names)."""

from __future__ import annotations

from typing import Any

from hopscope.probe.card import ProbeCard
from hopscope.probe.grammar import CardReading, read_card

SCHEMA = "hopscope.probe/v1"


def _tier(t: int | None) -> str | None:
    return None if t is None else f"T{t}"


def reading_to_dict(card: ProbeCard, reading: CardReading | None = None) -> dict[str, Any]:
    reading = reading if reading is not None else read_card(card)
    return {
        "schema": SCHEMA,
        "card": card.name,
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
        f"card {_safe(d['card'])}  tier {d['tier'] or '-'}  solicits {'YES' if d['solicits'] else 'no'}",
        f"  urls:      {join(d['urls'])}",
        f"  implied:   {join(d['implied'])}",
        f"  solicited: {join(d['solicited'])}",
        f"  oov:       {join(d['out_of_vocabulary'])}",
    ]
    for s in d["skills"]:
        flag = "  SOLICITS" if s["solicits"] else ""
        lines.append(f"  skill {_safe(s['id']):<24} tier {s['tier'] or '-'}{flag}")
    return "\n".join(lines)
