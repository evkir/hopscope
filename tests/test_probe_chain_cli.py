import json
from pathlib import Path

import httpx
import pytest

from hopscope import cli

FIX = Path(__file__).parent / "fixtures" / "dvaa" / "0.9.2" / "chain"
BOTH = ("manager.in.jsonl", "manager.out.jsonl")


def _lab(out: Path, names, status: int) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        for name in names:
            with (out / name).open("a", encoding="utf-8") as f:
                f.write((FIX / name).read_text(encoding="utf-8").strip() + "\n")
        return httpx.Response(status, json={"ok": True})

    return httpx.MockTransport(handler)


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    def _run(*extra, names=BOTH, status=200):
        monkeypatch.setattr(cli, "_PROBE_TRANSPORT", _lab(tmp_path, names, status))
        monkeypatch.setattr(cli, "_CHAIN_WAIT", 0.0)
        rc = cli.main(["probe", "dvaa-chain", "--records", str(tmp_path), *extra])
        out, err = capsys.readouterr()
        return rc, out, err

    return _run


def test_json_lists_chain_edges(run):
    rc, out, _ = run("--json")
    assert rc == 0
    edges = json.loads(out)
    assert len(edges) == 1 and edges[0]["schema"] == "hopscope.probe.chain/v1"


def test_text_report_names_the_hop(run):
    rc, out, _ = run()
    assert rc == 0 and "manager" in out


def test_unmatched_exits_4(run):
    rc, _, err = run(names=BOTH[:1])
    assert rc == 4 and "unmatched" in err


def test_http_error_exits_4(run):
    rc, _, err = run(names=(), status=500)
    assert rc == 4 and "HTTP 500" in err


def test_corrupt_records_exit_4(run, tmp_path):
    (tmp_path / "manager.in.jsonl").write_text("not json\n", encoding="utf-8")
    rc, _, err = run()
    assert rc == 4 and "bad json" in err


def test_default_records_dir_is_the_repo_lab():
    p = Path(cli._default_records())
    assert p.parts[-3:] == ("labs", "dvaa-chain", "out")
    assert (p / ".gitkeep").exists()


def test_sarif_file_carries_hsc004(run, tmp_path):
    sarif = tmp_path / "chain.sarif"
    rc, _, _ = run("--sarif", str(sarif))
    assert rc == 0
    results = json.loads(sarif.read_text(encoding="utf-8"))["runs"][0]["results"]
    assert [r["ruleId"] for r in results] == ["HSC004"]
    assert results[0]["properties"]["target"] == "dvaa-chain"


def test_sarif_on_a_card_target_exits_2(tmp_path, capsys):
    rc = cli.main(["probe", "dvaa-a", "--sarif", str(tmp_path / "x.sarif")])
    assert rc == 2 and "chain targets" in capsys.readouterr().err
    assert not (tmp_path / "x.sarif").exists()
