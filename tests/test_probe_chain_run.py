import json
from pathlib import Path

import httpx
import pytest

from hopscope.probe.chain import read_records
from hopscope.probe.chain_run import ChainError, probe_chain
from hopscope.targets import TargetRefused

FIX = Path(__file__).parent / "fixtures" / "dvaa" / "0.9.2" / "chain"
URL = "http://127.0.0.1:3130/analyze"
BOTH = ("manager.in.jsonl", "manager.out.jsonl")


def _lab(out: Path, names=BOTH, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path == "/analyze"
        assert json.loads(request.content) == {"quarter": "Q1"}
        for name in names:
            with (out / name).open("a", encoding="utf-8") as f:
                f.write((FIX / name).read_text(encoding="utf-8").strip() + "\n")
        headers = {"location": "http://127.0.0.1:1/"} if 300 <= status < 400 else None
        return httpx.Response(status, json={"ok": True}, headers=headers)

    return httpx.MockTransport(handler)


def _fixture_id() -> str:
    return str(read_records(FIX / "manager.in.jsonl")[0]["id"])


def test_reads_the_new_manager_edge(tmp_path):
    edges = probe_chain(URL, "manager", tmp_path, transport=_lab(tmp_path), wait=0)
    assert [e.task_id for e in edges] == [_fixture_id()]
    e = edges[0]
    assert e.hop == "manager" and e.escalated and e.origin_rewritten
    assert "_originalPermissions" in e.hidden_fields


def test_records_from_earlier_runs_are_ignored(tmp_path):
    for name in BOTH:
        line = json.loads((FIX / name).read_text(encoding="utf-8").strip())
        line["body"]["id"] = "old-1"
        (tmp_path / name).write_text(json.dumps(line) + "\n", encoding="utf-8")
    edges = probe_chain(URL, "manager", tmp_path, transport=_lab(tmp_path), wait=0)
    assert [e.task_id for e in edges] == [_fixture_id()]


def test_ingress_without_egress_is_unmatched(tmp_path):
    with pytest.raises(ChainError, match="unmatched.*in:"):
        probe_chain(URL, "manager", tmp_path, transport=_lab(tmp_path, names=BOTH[:1]), wait=0)


def test_no_new_records_is_unmatched(tmp_path):
    with pytest.raises(ChainError, match="no new records"):
        probe_chain(URL, "manager", tmp_path, transport=_lab(tmp_path, names=()), wait=0)


@pytest.mark.parametrize("status", [302, 500])
def test_non_2xx_is_an_error_and_redirects_are_not_followed(tmp_path, status):
    with pytest.raises(ChainError, match=f"HTTP {status}"):
        probe_chain(URL, "manager", tmp_path, transport=_lab(tmp_path, names=(), status=status), wait=0)


def test_remote_entry_point_is_refused_before_any_request(tmp_path):
    def boom(request):
        raise AssertionError("request sent to a refused target")

    with pytest.raises(TargetRefused):
        probe_chain("http://example.com/analyze", "manager", tmp_path, transport=httpx.MockTransport(boom), wait=0)


def test_transport_error_names_the_entry_point(tmp_path):
    def refuse(request):
        raise httpx.ConnectError("[Errno 111] Connection refused", request=request)

    with pytest.raises(ChainError, match=r"127\.0\.0\.1:3130/analyze: \[Errno 111\]"):
        probe_chain(URL, "manager", tmp_path, transport=httpx.MockTransport(refuse), wait=0)
