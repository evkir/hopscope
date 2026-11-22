from __future__ import annotations

from pathlib import Path

from hopscope.tools.authority import CLASS_WEIGHTS, T0, T1, T2

ROOT = Path(__file__).resolve().parents[1]
MAPPING = (ROOT / "docs" / "ppd-mapping.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_tier_sizes_in_doc_match_code() -> None:
    for name, mandate in (("T0", T0), ("T1", T1), ("T2", T2)):
        assert f"| {name} | {len(mandate.caps)} |" in MAPPING


def test_every_tier_grant_is_documented() -> None:
    for spec in T2.specs():
        assert f"`{spec}`" in MAPPING, spec


def test_weights_in_doc_match_code() -> None:
    assert sorted(CLASS_WEIGHTS.values()) == [1.0, 2.0, 3.0, 4.0]
    assert "read 1, local write 2, privileged 3, egress 4" in MAPPING


def test_readme_never_claims_mir() -> None:
    assert "CIR is not MIR" in README and "CIR is not MIR" in MAPPING
    assert "measures MIR" not in README
