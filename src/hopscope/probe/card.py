"""Tolerant reader for AgentCards published by external targets.

External agents publish cards from several A2A revisions (top-level ``url`` in 0.2/0.3,
``supportedInterfaces`` in 1.0), in camelCase or snake_case. The probe needs only what a
delegating hop reads, so it parses into its own small model instead of the SDK's strict types.
Everything in a card is attacker-controlled: this module records URLs and never follows them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MAX_SKILLS = 64
MAX_TEXT = 4096
_IFACE_KEYS = ("supportedInterfaces", "supported_interfaces", "additionalInterfaces", "additional_interfaces")


class CardError(ValueError):
    """The document is not a usable AgentCard."""


@dataclass(frozen=True, slots=True)
class ProbeSkill:
    id: str
    name: str
    description: str
    tags: tuple[str, ...] = ()

    def text(self) -> str:
        return " ".join((self.id, self.name, self.description, *self.tags))


@dataclass(frozen=True, slots=True)
class ProbeCard:
    name: str
    description: str
    urls: tuple[str, ...]
    skills: tuple[ProbeSkill, ...]
    extensions: tuple[str, ...] = ()
    source: str = "published"


def _text(value: Any, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CardError(f"{field} must be a string")
    return value[:MAX_TEXT]


def _skill(i: int, raw: Any) -> ProbeSkill:
    if not isinstance(raw, Mapping):
        raise CardError(f"skills[{i}] must be an object")
    sid = _text(raw.get("id"), f"skills[{i}].id") or f"skill-{i}"
    tags = raw.get("tags")
    tags = [] if tags is None else tags
    if not isinstance(tags, list):
        raise CardError(f"skills[{i}].tags must be a list")
    return ProbeSkill(
        id=sid,
        name=_text(raw.get("name"), f"skills[{i}].name") or sid,
        description=_text(raw.get("description"), f"skills[{i}].description"),
        tags=tuple(_text(t, f"skills[{i}].tags") for t in tags),
    )


def parse_card(doc: Any) -> ProbeCard:
    if not isinstance(doc, Mapping):
        raise CardError("AgentCard must be a JSON object")
    name = _text(doc.get("name"), "name")
    if not name:
        raise CardError("AgentCard has no name")

    urls: list[str] = []
    if doc.get("url"):
        urls.append(_text(doc["url"], "url"))
    for key in _IFACE_KEYS:
        for iface in doc.get(key) or ():
            if isinstance(iface, Mapping) and iface.get("url"):
                urls.append(_text(iface["url"], f"{key}.url"))

    raw_skills = doc.get("skills")
    raw_skills = [] if raw_skills is None else raw_skills
    if not isinstance(raw_skills, list):
        raise CardError("skills must be a list")
    if len(raw_skills) > MAX_SKILLS:
        raise CardError(f"card lists {len(raw_skills)} skills, limit is {MAX_SKILLS}")

    caps = doc.get("capabilities") or {}
    raw_ext = caps.get("extensions") or [] if isinstance(caps, Mapping) else []
    extensions = tuple(_text(e["uri"], "extensions.uri") for e in raw_ext if isinstance(e, Mapping) and e.get("uri"))

    return ProbeCard(
        name=name,
        description=_text(doc.get("description"), "description"),
        urls=tuple(dict.fromkeys(urls)),
        skills=tuple(_skill(i, s) for i, s in enumerate(raw_skills)),
        extensions=extensions,
    )
