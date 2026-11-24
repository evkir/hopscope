import json

import httpx
import pytest

import hopscope.cli as cli
from hopscope.probe.card import CardError
from hopscope.probe.dvaa import SOURCE, card_from_dashboard, fetch_dvaa_card
from hopscope.probe.grammar import read_card

# Subset of DVAA 0.9.2 GET :9000/agents, fields as observed on 2026-11-24.
AGENTS = [
    {"id": "orchestrator", "name": "Orchestrator", "port": 7020, "protocol": "a2a", "securityLevel": "standard",
     "description": "Multi-agent orchestrator that delegates tasks", "tools": [], "vulnerabilities": ["agentToAgent"]},
    {"id": "worker-1", "name": "Worker Agent", "port": 7021, "protocol": "a2a", "securityLevel": "weak",
     "description": "Worker agent that executes delegated tasks", "tools": ["read_file", "write_file", "fetch_url"]},
]


def test_worker_card_is_synthesized_and_reads_as_t2():
    card = card_from_dashboard(AGENTS, "worker-1")
    assert card.source == SOURCE
    assert card.urls == ("http://127.0.0.1:7021/",)
    assert [s.id for s in card.skills] == ["read_file", "write_file", "fetch_url"]
    reading = read_card(card)
    assert {"fs:read:/workspace/*", "fs:write:/workspace/*", "net:fetch:*"} <= set(reading.implied.specs())
    assert reading.tier == 2
    assert not reading.solicits


def test_orchestrator_has_no_tools_and_no_tier():
    assert read_card(card_from_dashboard({"agents": AGENTS}, "orchestrator")).tier is None


@pytest.mark.parametrize(("doc", "agent"), [({"x": 1}, "worker-1"), (AGENTS, "nope"), ([{"id": "a", "tools": "x"}], "a")])
def test_bad_dashboard_documents(doc, agent):
    with pytest.raises(CardError):
        card_from_dashboard(doc, agent)


def test_fetch_and_cli(monkeypatch, capsys):
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=AGENTS))
    assert fetch_dvaa_card("worker-1", transport=transport).name == "Worker Agent"
    monkeypatch.setattr(cli, "_PROBE_TRANSPORT", transport)
    assert cli.main(["probe", "dvaa-b", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert (d["card_source"], d["tier"]) == (SOURCE, "T2")
