import json
from pathlib import Path

import pytest

from hopscope.probe.chain import pair_records, read_edge, read_records

CHAIN = Path(__file__).parent / "fixtures" / "dvaa" / "0.9.2" / "chain"
BASE = {"id": "t1", "from": "a", "permissions": ["read-write"], "context": "do x"}


def _recorded():
    (i,) = read_records(CHAIN / "manager.in.jsonl")
    (o,) = read_records(CHAIN / "manager.out.jsonl")
    return i, o


def test_recorded_manager_hop_is_poisoned_on_every_axis():
    e = read_edge("manager", *_recorded())
    assert sorted(map(str, e.excess)) == ["fs:write:/workspace/*", "net:fetch:*", "net:post:*"]
    assert e.oov_added == ("exec",)
    assert e.origin_rewritten and e.context_appended and not e.context_rewritten
    assert e.hidden_fields == ("_originalPermissions",)
    assert e.escalated and e.poisoned
    assert e.context_out.length > e.context_in.length


def test_digest_never_carries_context_text():
    e = read_edge("manager", *_recorded())
    assert "API keys" not in repr(e)
    assert len(e.context_out.sha256) == 16


def test_clean_passthrough_has_no_findings():
    e = read_edge("h", BASE, dict(BASE))
    assert not e.poisoned
    assert e.excess == frozenset()


def test_attenuation_is_not_excess():
    e = read_edge("h", BASE, {**BASE, "permissions": ["read-only"]})
    assert e.excess == frozenset()
    assert not e.escalated


def test_rewritten_context_is_not_append():
    e = read_edge("h", BASE, {**BASE, "context": "do y"})
    assert (e.context_appended, e.context_rewritten) == (False, True)


def test_preexisting_underscore_field_is_not_hidden():
    i = {**BASE, "_trace": 1}
    assert read_edge("h", i, dict(i)).hidden_fields == ()


def test_mismatched_tasks_and_non_objects_raise():
    with pytest.raises(ValueError):
        read_edge("h", BASE, {**BASE, "id": "t2"})
    with pytest.raises(ValueError):
        read_edge("h", BASE, ["not", "an", "object"])


def test_read_records_filters_paths_and_rejects_bad_json(tmp_path):
    p = tmp_path / "x.jsonl"
    rows = [
        {"path": "/tasks/send", "body": BASE},
        {"path": "/collect", "body": {"x": 1}},
        {"path": "/tasks/send", "body": "str"},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n\n", encoding="utf-8")
    assert read_records(p) == [BASE]
    p.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"x\.jsonl:1"):
        read_records(p)


def test_pair_records_reports_unmatched():
    a, b, c = ({**BASE, "id": x} for x in "abc")
    pairs, unmatched = pair_records([a, b], [b, c])
    assert pairs == [(b, b)]
    assert unmatched == ("in:a", "out:c")
