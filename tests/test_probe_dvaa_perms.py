import json
from pathlib import Path

import pytest

from hopscope.probe.dvaa_perms import PERMISSION_CAPS, PERMISSION_OOV, read_permissions
from hopscope.probe.grammar import OOV_RULES, tier_of
from hopscope.tools.caps import Capability

CHAIN = Path(__file__).parent / "fixtures" / "dvaa" / "0.9.2" / "chain"


def _body(name: str) -> dict:
    lines = (CHAIN / name).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])["body"]


def test_every_mapped_spec_has_a_tier():
    for label, specs in PERMISSION_CAPS.items():
        for spec in specs:
            assert tier_of(Capability.parse(spec)) is not None, (label, spec)


def test_oov_labels_match_card_grammar():
    assert set(PERMISSION_OOV.values()) <= {label for _, label in OOV_RULES}


@pytest.mark.parametrize(
    ("labels", "tier"),
    [(["read-only"], 0), (["read-write"], 1), (["network-access"], 2), (["read-only", "network-access"], 2)],
)
def test_tier_is_derived(labels, tier):
    assert read_permissions(labels).tier == tier


def test_execute_is_oov_not_a_capability():
    r = read_permissions(["execute"])
    assert r.oov == ("exec",)
    assert r.mandate.caps == frozenset()
    assert r.tier is None


def test_unknown_labels_kept_verbatim_and_normalised():
    r = read_permissions([" Read-Only ", "read-only", "sudo", ""])
    assert r.labels == ("read-only", "sudo")
    assert r.unmapped == ("sudo",)
    assert r.mandate.specs() == ("fs:read:/workspace/*",)


@pytest.mark.parametrize("bad", [None, "read-only", ["read-only", 1], {"read-only": True}])
def test_rejects_non_list_of_strings(bad):
    with pytest.raises(ValueError):
        read_permissions(bad)


def test_recorded_manager_hop_escalates_t0_to_t2():
    held = read_permissions(_body("manager.in.jsonl")["permissions"])
    granted = read_permissions(_body("manager.out.jsonl")["permissions"])
    assert (held.tier, granted.tier) == (0, 2)
    assert (held.oov, granted.oov) == ((), ("exec",))
    excess = sorted(str(c) for c in held.mandate.excess(granted.mandate))
    assert excess == ["fs:write:/workspace/*", "net:fetch:*", "net:post:*"]


def test_recorded_hidden_field_preserves_original_permissions():
    out = _body("manager.out.jsonl")
    assert out["_originalPermissions"] == _body("manager.in.jsonl")["permissions"]
