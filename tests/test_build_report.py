from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hopscope.cli import main
from hopscope.report.build import build_report
from hopscope.report.journal import read_jsonl


def test_build_report_writes_three_files(tmp_path: Path) -> None:
    paths = asyncio.run(build_report(tmp_path, 1))
    assert len(read_jsonl(paths["jsonl"])) == 9
    assert json.loads(paths["sarif"].read_text())["version"] == "2.1.0"
    assert "CIR is not MIR" in paths["html"].read_text()


def test_cli_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["report", "--n", "1", "--out", str(tmp_path / "r")]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [line.split(":")[0] for line in out] == ["jsonl", "sarif", "html"]
    assert (tmp_path / "r" / "report.html").exists()
