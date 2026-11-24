import pytest

from hopscope.probe.card import MAX_SKILLS, MAX_TEXT, CardError, parse_card

V03 = {
    "name": "Orchestrator",
    "description": "Delegates tasks",
    "url": "http://127.0.0.1:7020/",
    "skills": [{"id": "delegate", "name": "Delegate", "description": "Send work to a worker", "tags": ["a2a"]}],
}

V10 = {
    "name": "worker",
    "supportedInterfaces": [
        {"url": "http://127.0.0.1:7021/", "protocolBinding": "JSONRPC"},
        {"url": "http://127.0.0.1:7021/"},
    ],
    "capabilities": {"extensions": [{"uri": "urn:x:mandate"}, {"description": "no uri"}]},
    "skills": [],
}


def test_parses_v03_top_level_url():
    card = parse_card(V03)
    assert card.urls == ("http://127.0.0.1:7020/",)
    assert card.skills[0].id == "delegate"
    assert "a2a" in card.skills[0].text()


def test_parses_v10_interfaces_dedupes_urls_and_reads_extensions():
    card = parse_card(V10)
    assert card.urls == ("http://127.0.0.1:7021/",)
    assert card.extensions == ("urn:x:mandate",)
    assert card.description == ""


def test_skill_defaults_fill_missing_id_and_name():
    card = parse_card({"name": "x", "skills": [{"description": "d"}]})
    assert (card.skills[0].id, card.skills[0].name) == ("skill-0", "skill-0")


def test_long_text_is_truncated():
    card = parse_card({"name": "x", "description": "a" * (MAX_TEXT + 10)})
    assert len(card.description) == MAX_TEXT


@pytest.mark.parametrize(
    "doc",
    [
        [],
        {"description": "no name"},
        {"name": 3},
        {"name": "x", "skills": {}},
        {"name": "x", "skills": ["s"]},
        {"name": "x", "skills": [{"tags": "a2a"}]},
        {"name": "x", "skills": [{}] * (MAX_SKILLS + 1)},
    ],
)
def test_rejects_malformed_cards(doc):
    with pytest.raises(CardError):
        parse_card(doc)
