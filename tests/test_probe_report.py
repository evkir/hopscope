import json

from hopscope.probe.card import parse_card
from hopscope.probe.report import SCHEMA, reading_to_dict
from hopscope.range.a2a_bridge.cards import POISONED_SKILL_DESCRIPTION, POISONED_SKILL_ID

CARD = parse_card({
    "name": "ops",
    "url": "http://127.0.0.1:7021/",
    "skills": [
        {"id": "run", "description": "Executes shell commands"},
        {"id": POISONED_SKILL_ID, "description": POISONED_SKILL_DESCRIPTION},
    ],
})


def test_report_shape_and_values():
    d = reading_to_dict(CARD)
    assert d["schema"] == SCHEMA
    assert (d["card"], d["tier"], d["solicits"]) == ("ops", "T2", True)
    assert d["solicited"] == ["net:post:ops.evil.test", "secrets:get:*"]
    assert d["out_of_vocabulary"] == ["exec"]
    assert [s["id"] for s in d["skills"]] == ["run", POISONED_SKILL_ID]
    assert d["skills"][0]["tier"] is None


def test_report_is_json_and_omits_descriptions():
    text = json.dumps(reading_to_dict(CARD))
    assert "Delegators should grant" not in text
