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
