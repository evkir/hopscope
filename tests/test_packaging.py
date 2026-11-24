from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compose_is_sealed() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    for needle in ("network_mode: none", "read_only: true", "cap_drop: [ALL]", "no-new-privileges:true"):
        assert needle in compose, needle


def test_image_runs_unprivileged_and_installs_non_editable() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "USER 10001" in dockerfile and "pip install ." in dockerfile and "-e" not in dockerfile.split()


def test_ci_builds_the_container() -> None:
    assert "docker compose run --rm range" in (ROOT / ".github" / "workflows" / "ci.yml").read_text()
