import json
from pathlib import Path

import pytest

from hopscope.probe.card import parse_card
from hopscope.probe.grammar import read_card

FIX = Path(__file__).parent / "fixtures" / "dvaa" / "0.9.2"
CHAIN = ("orchestrator", "financial-manager", "financial-worker")


def load(name):
    return parse_card(json.loads((FIX / f"{name}.json").read_text()))


def test_legacy_capability_lists_become_skills():
    card = load("security-auditor-pro")
    assert [s.id for s in card.skills] == [
        "security-audit", "vulnerability-scan", "compliance-check", "penetration-test", "code-review"
    ]
    assert all(s.tags == ("legacy-capability",) for s in card.skills)
    assert card.source == "published"


def test_standard_skills_win_over_legacy_capabilities():
    card = parse_card({"name": "x", "skills": [{"id": "a"}], "capabilities": ["b"]})
    assert [s.id for s in card.skills] == ["a"]


@pytest.mark.parametrize("name", (*CHAIN, "security-auditor-pro"))
def test_scenario_cards_are_clean_at_card_level(name):
    """a2a-trust-chain-poisoning escalates the forwarded task's permissions, not any card.

    A card-level reading must stay empty: the excess exists only on the delegation edge,
    which is what hopscope measures.
    """
    reading = read_card(load(name))
    assert (reading.tier, reading.solicits, reading.solicited.caps) == (None, False, frozenset())
