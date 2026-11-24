import httpx
import pytest

import hopscope.cli as cli
from hopscope.probe.discover import WELL_KNOWN, discover_card
from hopscope.probe.fetch import FetchError
from hopscope.targets import TargetRefused

CARD = {"name": "worker", "url": "http://127.0.0.1:3132/", "skills": []}


def serving(routes):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        status, body = routes.get(request.url.path, (404, None))
        return httpx.Response(status, json=body) if body is not None else httpx.Response(status)

    return httpx.MockTransport(handler), seen


def test_prefers_v03_path():
    transport, seen = serving({WELL_KNOWN[0]: (200, CARD), WELL_KNOWN[1]: (200, {"name": "old"})})
    assert discover_card("http://127.0.0.1:3132", transport=transport).name == "worker"
    assert seen == [WELL_KNOWN[0]]


def test_falls_back_to_v02_path_from_host_root():
    transport, seen = serving({WELL_KNOWN[1]: (200, CARD)})
    assert discover_card("http://127.0.0.1:3132/a2a/rpc", transport=transport).name == "worker"
    assert seen == list(WELL_KNOWN)


def test_no_card_anywhere():
    transport, _ = serving({})
    with pytest.raises(FetchError, match="no AgentCard") as exc:
        discover_card("http://127.0.0.1:3132/", transport=transport)
    assert exc.value.status == 404


def test_non_404_is_final_no_fallback():
    transport, seen = serving({WELL_KNOWN[0]: (500, None)})
    with pytest.raises(FetchError, match="500"):
        discover_card("http://127.0.0.1:3132/", transport=transport)
    assert seen == [WELL_KNOWN[0]]


def test_remote_base_refused():
    with pytest.raises(TargetRefused):
        discover_card("https://agent.example.com/")


def test_cli_uses_discovery_for_base_urls(monkeypatch, capsys):
    transport, seen = serving({WELL_KNOWN[1]: (200, CARD)})
    monkeypatch.setattr(cli, "_PROBE_TRANSPORT", transport)
    assert cli.main(["probe", "http://127.0.0.1:3132/"]) == 0
    assert "card worker [published]" in capsys.readouterr().out
    assert seen == list(WELL_KNOWN)
