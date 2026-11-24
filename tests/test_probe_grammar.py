import pytest

from hopscope.probe.card import ProbeSkill, parse_card
from hopscope.probe.grammar import read_card, read_skill, tier_of
from hopscope.range.a2a_bridge.cards import POISONED_SKILL_DESCRIPTION, POISONED_SKILL_ID, ROLE_DESCRIPTIONS
from hopscope.tools.caps import Capability


def skill(description, sid="s", tags=()):
    return ProbeSkill(sid, sid, description, tuple(tags))


def test_poisoned_skill_solicits_t2_authority():
    r = read_skill(skill(POISONED_SKILL_DESCRIPTION, POISONED_SKILL_ID, ["ops"]))
    assert r.solicits
    assert r.solicited.specs() == ("net:post:ops.evil.test", "secrets:get:*")
    assert {"secrets:get:*", "net:post:*"} <= set(r.implied.specs())
    assert r.tier == 2


@pytest.mark.parametrize("role", sorted(ROLE_DESCRIPTIONS))
def test_hopscope_role_cards_do_not_solicit(role):
    r = read_skill(skill(ROLE_DESCRIPTIONS[role], role, ["hopscope", role]))
    assert not r.solicits
    assert not r.solicited.caps
    assert r.tier is None


def test_executor_claims_out_of_vocabulary_exec():
    assert read_skill(skill(ROLE_DESCRIPTIONS["executor"], "executor")).out_of_vocabulary == ("exec",)


@pytest.mark.parametrize(
    ("description", "spec", "tier"),
    [
        ("Reads files from the shared workspace", "fs:read:/workspace/*", 0),
        ("Lists files in a folder", "fs:list:/workspace/*", 0),
        ("Shows the account balance", "payments:balance:*", 0),
        ("Saves generated documents", "fs:write:/workspace/*", 1),
        ("Deletes old files", "fs:delete:/workspace/*", 1),
        ("Rotates API keys for services", "secrets:get:*", 2),
        ("Downloads a URL and summarises it", "net:fetch:*", 2),
        ("Pays supplier invoices", "payments:transfer:*", 2),
        ("Sends the report to a webhook endpoint", "net:post:*", 2),
    ],
)
def test_keyword_rules(description, spec, tier):
    r = read_skill(skill(description))
    assert spec in r.implied.specs()
    assert r.tier == tier
    assert not r.solicits


def test_dvaa_style_worker_is_oov_not_tiered():
    r = read_skill(skill("Executes shell commands sent by the orchestrator", "execute"))
    assert r.out_of_vocabulary == ("exec",)
    assert r.tier is None


def test_tier_of():
    assert tier_of(Capability.parse("fs:read:/workspace/a.txt")) == 0
    assert tier_of(Capability.parse("secrets:get:db")) == 2
    assert tier_of(Capability.parse("fs:read:/etc/passwd")) is None


def test_read_card_aggregates_skills():
    card = parse_card({
        "name": "ops",
        "url": "http://127.0.0.1:7021/",
        "skills": [
            {"id": "files", "description": "Reads files from the workspace"},
            {"id": POISONED_SKILL_ID, "description": POISONED_SKILL_DESCRIPTION},
        ],
    })
    reading = read_card(card)
    assert reading.solicits
    assert reading.tier == 2
    assert "fs:read:/workspace/*" in reading.implied.specs()
    assert reading.solicited.specs() == ("net:post:ops.evil.test", "secrets:get:*")
