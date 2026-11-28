from __future__ import annotations

import tomllib
from pathlib import Path

from hopscope import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_versions_agree() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__ == "0.2.0"


def test_citation_and_changelog_carry_the_version() -> None:
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert f"version: {__version__}" in citation and "10.5281/zenodo.23513214" in citation
    assert f"## [{__version__}]" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
