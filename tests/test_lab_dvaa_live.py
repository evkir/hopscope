"""Live lab: labs/dvaa-chain up, one probe, HSC004 on the manager edge. Run with ``pytest -m dvaa``."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from hopscope import cli

pytestmark = pytest.mark.dvaa

LAB = Path(__file__).resolve().parents[1] / "labs" / "dvaa-chain"


def _compose(*args: str) -> None:
    env = {**os.environ, "HOPSCOPE_UID": str(os.getuid()), "HOPSCOPE_GID": str(os.getgid())}
    subprocess.run(["docker", "compose", *args], cwd=LAB, env=env, check=True, timeout=180)


@pytest.fixture(scope="module")
def lab():
    if shutil.which("docker") is None:
        pytest.skip("docker not installed")
    _compose("up", "-d")
    try:
        yield
    finally:
        _compose("down")


def test_live_manager_edge_is_hsc004(lab, tmp_path, capsys):
    sarif = tmp_path / "chain.sarif"
    deadline = time.monotonic() + 60
    while True:
        rc = cli.main(["probe", "dvaa-chain", "--json", "--sarif", str(sarif)])
        out, err = capsys.readouterr()
        if rc == 0 or time.monotonic() > deadline:
            break
        time.sleep(2)
    assert rc == 0, err
    assert len(json.loads(out)) == 1
    results = json.loads(sarif.read_text(encoding="utf-8"))["runs"][0]["results"]
    assert [r["ruleId"] for r in results] == ["HSC004"]
    props = results[0]["properties"]
    assert (props["held_tier"], props["granted_tier"]) == ("T0", "T2")
    assert "oov:exec" in props["excess"]
    assert props["origin_rewritten"] and props["context_appended"]
    assert "_originalPermissions" in props["hidden_fields"]
