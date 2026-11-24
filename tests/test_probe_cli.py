import json

import httpx
import pytest

import hopscope.cli as cli
from hopscope.range.a2a_bridge.cards import POISONED_SKILL_DESCRIPTION, POISONED_SKILL_ID

CARD = {
    "name": "ops\x1b[2K\x1b[32m",
    "url": "http://127.0.0.1:7021/",
    "skills": [{"id": POISONED_SKILL_ID, "description": POISONED_SKILL_DESCRIPTION}],
}


@pytest.fixture
def serve(monkeypatch):
    def _serve(doc, status=200):
        monkeypatch.setattr(cli, "_PROBE_TRANSPORT", httpx.MockTransport(lambda r: httpx.Response(status, json=doc)))

    return _serve


def test_probe_known_target_json(serve, capsys):
    serve(CARD)
    assert cli.main(["probe", "dvaa-b", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert (d["tier"], d["solicits"]) == ("T2", True)


def test_probe_human_output_strips_control_sequences(serve, capsys):
    serve(CARD)
    assert cli.main(["probe", "http://127.0.0.1:7021/.well-known/agent-card.json"]) == 0
    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "tier T2" in out and "solicits YES" in out and "SOLICITS" in out


def test_probe_refuses_remote_target(capsys):
    assert cli.main(["probe", "https://agent.example.com/.well-known/agent-card.json"]) == 3
    assert "refused" in capsys.readouterr().err


def test_probe_reports_fetch_errors(serve, capsys):
    serve({}, status=404)
    assert cli.main(["probe", "dvaa-a"]) == 4
    assert "404" in capsys.readouterr().err
