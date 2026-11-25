import json
from pathlib import Path

from hopscope.probe.chain import read_edge, read_records
from hopscope.probe.report import CHAIN_SCHEMA, edge_to_dict, format_edge

CHAIN = Path(__file__).parent / "fixtures" / "dvaa" / "0.9.2" / "chain"


def _recorded_dict():
    (i,) = read_records(CHAIN / "manager.in.jsonl")
    (o,) = read_records(CHAIN / "manager.out.jsonl")
    return edge_to_dict(read_edge("manager", i, o), target="dvaa-chain")


def test_chain_report_schema_and_findings():
    d = _recorded_dict()
    assert d["schema"] == CHAIN_SCHEMA == "hopscope.probe.chain/v1"
    assert (d["held"]["tier"], d["granted"]["tier"]) == ("T0", "T2")
    assert d["excess"] == ["fs:write:/workspace/*", "net:fetch:*", "net:post:*"]
    assert d["oov_added"] == ["exec"]
    assert d["flags"]["hidden_fields"] == ["_originalPermissions"]
    assert d["escalated"] and d["poisoned"]


def test_chain_report_carries_no_context_text():
    blob = json.dumps(_recorded_dict())
    for leak in ("API keys", "ADDITIONAL CONTEXT", "/collect"):
        assert leak not in blob


def test_format_edge_poisoned():
    text = format_edge(_recorded_dict())
    assert "POISONED" in text
    assert "EXCESS:   fs:write:/workspace/*, net:fetch:*, net:post:*, oov:exec" in text
    assert "hidden _originalPermissions" in text


def test_format_edge_clean_and_sanitised():
    body = {"id": "t\x1b]0;x\x07", "from": "a", "permissions": ["\x1b[31mread-only"], "context": "c"}
    text = format_edge(edge_to_dict(read_edge("h\x1b[2J", body, dict(body)), target="t"))
    assert "clean" in text and "EXCESS:   -" in text
    assert "\x1b" not in text and "\x07" not in text
