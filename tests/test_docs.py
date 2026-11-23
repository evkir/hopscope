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


def test_readme_matrix_is_generated_from_code() -> None:
    import asyncio
    import re

    from hopscope.meter.matrix import format_matrix, run_matrix

    m = re.search(r"<!-- matrix:start -->\n```text\n(.*?)\n```\n<!-- matrix:end -->", README, re.S)
    assert m is not None and m.group(1) == format_matrix(asyncio.run(run_matrix(3)))


def test_readme_documents_exploratory_metrics_and_live_mode() -> None:
    assert "## Exploratory metrics (not pre-registered)" in README
    assert "hopscope live --model" in README and "exits with code 3" in README
