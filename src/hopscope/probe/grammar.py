"""Capability grammar: read an external AgentCard into hopscope's capability vocabulary.

A delegating hop decides what to hand its peer from the peer's card, so the card is where
over-delegation starts. Each skill is read into (a) capabilities it implies, by keyword rules
over the simulated vocabulary in ``tools.authority.GRANTS``; (b) capabilities its text
explicitly solicits, as literal ``domain:action:resource`` specs (the poisoned-card pattern);
and (c) the lowest authority tier T0-T2 covering them. This is a deterministic, tested
heuristic, not a classifier: anything outside the simulated vocabulary is reported as
out-of-vocabulary instead of being guessed into a tier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hopscope.probe.card import ProbeCard, ProbeSkill
from hopscope.tools.authority import GRANTS
from hopscope.tools.caps import Capability, Mandate

_S = r"[^.]{0,60}"  # stay inside one sentence

#: (pattern, capability) - matched case-insensitively against id, name, description and tags.
IMPLY_RULES: tuple[tuple[str, str], ...] = (
    (rf"\b(list\w*|browse\w*)\b{_S}\b(files?|director(?:y|ies)|folders?)\b", "fs:list:/workspace/*"),
    (rf"\b(read\w*|view\w*|open\w*)\b{_S}\b(files?|documents?)\b", "fs:read:/workspace/*"),
    (rf"\b(writ\w*|sav\w*|edit\w*|creat\w*)\b{_S}\b(files?|documents?)\b", "fs:write:/workspace/*"),
    (rf"\b(delet\w*|remov\w*)\b{_S}\b(files?|documents?)\b", "fs:delete:/workspace/*"),
    (r"\b(credentials?|secrets?|passwords?|api[ -]?keys?|tokens?)\b", "secrets:get:*"),
    (r"\bbalances?\b", "payments:balance:*"),
    (r"\b(pay|payments?|transfers?|invoices?|refunds?|wire)\b", "payments:transfer:*"),
    (r"\b(fetch\w*|download\w*|crawl\w*|urls?|https?)\b", "net:fetch:*"),
    (rf"\b(posts?|posting|webhooks?|exfiltrat\w*|send\w*{_S}\bendpoints?|backs? up{_S}\bendpoints?)\b", "net:post:*"),
)

#: Abilities a card may claim that the simulated tools cannot express.
OOV_RULES: tuple[tuple[str, str], ...] = (
    (r"\b(exec\w*|shell|commands?|subprocess\w*)\b", "exec"),
    (r"\b(sql|databases?|quer(?:y|ies))\b", "db"),
)

_SPEC = re.compile(r"\b(?:fs|secrets|payments|net):[\w*.-]+:[\w*./:-]+")
_SOLICIT = re.compile(
    rf"\b(grant\w*|give\w*|delegat\w*|assign\w*)\b{_S}\b(this agent|me|us|access|permissions?|privileges?|scopes?)\b",
    re.IGNORECASE,
)


def tier_of(cap: Capability) -> int | None:
    """Lowest tier whose grant covers ``cap``; None if no tier does (GRANTS is ordered by tier)."""
    for g in GRANTS:
        if Capability.parse(g.spec).covers(cap):
            return g.tier
    return None


def _max_tier(caps: frozenset[Capability]) -> int | None:
    return max((t for c in caps if (t := tier_of(c)) is not None), default=None)


def _union(mandates: list[Mandate]) -> Mandate:
    return Mandate(frozenset().union(*(m.caps for m in mandates)))


@dataclass(frozen=True, slots=True)
class SkillReading:
    skill_id: str
    implied: Mandate
    solicited: Mandate
    out_of_vocabulary: tuple[str, ...]
    solicits: bool

    @property
    def tier(self) -> int | None:
        return _max_tier(self.implied.caps | self.solicited.caps)


@dataclass(frozen=True, slots=True)
class CardReading:
    name: str
    skills: tuple[SkillReading, ...]

    @property
    def implied(self) -> Mandate:
        return _union([s.implied for s in self.skills])

    @property
    def solicited(self) -> Mandate:
        return _union([s.solicited for s in self.skills])

    @property
    def tier(self) -> int | None:
        return _max_tier(self.implied.caps | self.solicited.caps)

    @property
    def solicits(self) -> bool:
        return any(s.solicits for s in self.skills)


def read_skill(skill: ProbeSkill) -> SkillReading:
    text = skill.text()
    implied = Mandate.of(*sorted({spec for pat, spec in IMPLY_RULES if re.search(pat, text, re.IGNORECASE)}))
    solicited = Mandate.of(*sorted({m.rstrip(".,;:") for m in _SPEC.findall(text)}))
    oov = tuple(sorted({label for pat, label in OOV_RULES if re.search(pat, text, re.IGNORECASE)}))
    return SkillReading(skill.id, implied, solicited, oov, bool(solicited.caps) or bool(_SOLICIT.search(text)))


def read_card(card: ProbeCard) -> CardReading:
    return CardReading(card.name, tuple(read_skill(s) for s in card.skills))
