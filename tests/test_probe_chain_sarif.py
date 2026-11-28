import json
from pathlib import Path

import pytest

from hopscope.probe.chain import read_edge, read_records
from hopscope.report.sarif import RULES, edges_to_sarif

CHAIN = Path(__file__).parent / "fixtures" / "dvaa" / "0.9.2" / "chain"
BASE = {"id": "t1", "from": "a", "permissions": ["read-only"], "context": "c"}


def _recorded():
    (i,) = read_records(CHAIN / "manager.in.jsonl")
    (o,) = read_records(CHAIN / "manager.out.jsonl")
    return read_edge("manager", i, o)


def test_recorded_hop_emits_one_hsc004():
    doc = edges_to_sarif([_recorded()], version="0.2.0.dev", target="dvaa-chain")
    (r,) = doc["runs"][0]["results"]
    assert (r["ruleId"], r["level"]) == ("HSC004", "warning")
    assert r["message"]["text"].startswith(
        "manager delegated fs:write:/workspace/*, net:fetch:*, net:post:*, oov:exec beyond what it held"
    )
    p = r["properties"]
    assert (p["held_tier"], p["granted_tier"]) == ("T0", "T2")
    assert p["origin_rewritten"] and p["context_appended"]
    assert p["hidden_fields"] == ["_originalPermissions"]


def test_same_driver_and_rules_as_range():
    doc = edges_to_sarif([], version="x", target="t")
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["tool"]["driver"]["rules"] == list(RULES)
    assert doc["runs"][0]["results"] == []


def test_clean_and_attenuating_edges_emit_nothing():
    clean = read_edge("h", BASE, dict(BASE))
    weaker = read_edge("h", {**BASE, "permissions": ["read-write"]}, BASE)
    assert edges_to_sarif([clean, weaker], version="x", target="t")["runs"][0]["results"] == []


def test_sarif_carries_no_context_text():
    blob = json.dumps(edges_to_sarif([_recorded()], version="x", target="dvaa-chain"))
    for leak in ("API keys", "ADDITIONAL CONTEXT", "/collect"):
        assert leak not in blob


def test_target_controlled_strings_are_sanitised():
    bad = {**BASE, "id": "t\x1b[2J", "permissions": ["network-access"]}
    e = read_edge("h", {**BASE, "id": "t\x1b[2J"}, bad)
    (r,) = edges_to_sarif([e], version="x", target="t")["runs"][0]["results"]
    assert "\x1b" not in r["message"]["text"]
    assert "\x1b" not in r["properties"]["task_id"]


def test_tampered_edge_without_gain_emits_hsc005():
    e = read_edge("h", BASE, {**BASE, "from": "x"})
    (r,) = edges_to_sarif([e], version="x", target="t")["runs"][0]["results"]
    assert (r["ruleId"], r["level"]) == ("HSC005", "note")
    assert r["message"]["text"] == "h tampered with the delegation (origin_rewritten) without privilege gain (task t1)"
    p = r["properties"]
    assert p["excess"] == [] and p["origin_rewritten"] and (p["held_tier"], p["granted_tier"]) == ("T0", "T0")


@pytest.mark.parametrize(("out", "flags"), [
    ({"from": "x"}, ["origin_rewritten"]),
    ({"context": "c more"}, ["context_appended"]),
    ({"context": "z"}, ["context_rewritten"]),
    ({"_x": 1}, ["hidden_fields"]),
    ({"from": "x", "context": "z", "_x": 1}, ["origin_rewritten", "context_rewritten", "hidden_fields"]),
])
def test_hsc005_names_each_tampering_flag(out, flags):
    e = read_edge("h", BASE, {**BASE, **out})
    (r,) = edges_to_sarif([e], version="x", target="t")["runs"][0]["results"]
    assert r["ruleId"] == "HSC005"
    assert f"({', '.join(flags)})" in r["message"]["text"]
    p = r["properties"]
    assert [k for k in ("origin_rewritten", "context_appended", "context_rewritten") if p[k]] == [
        f for f in flags if f != "hidden_fields"
    ]
    assert p["hidden_fields"] == (["_x"] if "hidden_fields" in flags else [])
