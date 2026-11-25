"""Contract of labs/dvaa-chain: loopback-only, pinned, isolated. Text-level, no YAML dependency."""

import re
from pathlib import Path

LAB = Path(__file__).resolve().parents[1] / "labs" / "dvaa-chain"
COMPOSE = (LAB / "compose.yml").read_text(encoding="utf-8")
RECORDER = (LAB / "recorder.js").read_text(encoding="utf-8")
DIGEST = "sha256:edcd7fbb94b28be64527b58f7238384d58d9b0b015b6ab02cd7f816c7f696f45"


def _lines() -> list[str]:
    return [ln.split("#", 1)[0].rstrip() for ln in COMPOSE.splitlines()]


def test_only_orchestrator_published_on_loopback():
    ports = [ln for ln in _lines() if re.match(r"\s*ports:", ln)]
    assert ports == ['    ports: ["127.0.0.1:3130:3130"]']


def test_single_image_pinned_by_digest():
    images = [ln.strip() for ln in _lines() if ln.strip().startswith("image:")]
    assert images == [f"image: opena2a/dvaa:0.9.2@{DIGEST}"]


def test_chain_network_is_internal():
    assert re.search(r"\n  chain:\n    internal: true\n", COMPOSE)


def test_dvaa_hostnames_resolve_to_recorders():
    assert COMPOSE.count("aliases: [manager]") == 1
    assert COMPOSE.count("aliases: [worker]") == 1
    assert "UPSTREAM: http://dvaa-manager:3131" in COMPOSE


def test_hardening_present_and_no_escape_hatches():
    for needle in ("read_only: true", "cap_drop: [ALL]", '"no-new-privileges:true"', "init: true"):
        assert needle in COMPOSE, needle
    for banned in ("privileged", "network_mode", "/var/run/docker.sock", "cap_add"):
        assert banned not in COMPOSE, banned


def test_recorder_is_dependency_free_and_inert():
    requires = set(re.findall(r"require\('([^']+)'\)", RECORDER))
    assert requires == {"node:http", "node:fs", "node:path"}
    for banned in ("child_process", "eval(", "new Function"):
        assert banned not in RECORDER, banned
    assert RECORDER.count("fetch(") == 1  # tap forward only; sink never calls out


def test_recorder_output_not_committed():
    assert (LAB / ".gitignore").read_text(encoding="utf-8").split() == ["out/*", "!out/.gitkeep"]
