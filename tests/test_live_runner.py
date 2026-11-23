from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from hopscope.cli import main
from hopscope.harness.gpu_guard import LOCK_ENV, GPUBusy
from hopscope.harness.llm_client import FreshLoadOllama, OllamaConfig
from hopscope.live.runner import LiveCell, run_live_cell
from hopscope.range.demo import DEMO_SCRIPT
from hopscope.tools.gate import Ruling

ROLES = ("orchestrator", "planner", "worker", "executor")
CELL = LiveCell("qwen3:14b", False, None, "A0")


class OllamaSim:
    """Offline Ollama: answers /api/chat by the role named in the system prompt."""

    def __init__(self, n: int) -> None:
        self.queues = {k: list(v) * n for k, v in DEMO_SCRIPT.items()}
        self.chat: list[dict[str, Any]] = []

    def __call__(self, url: str, payload: Any, timeout: float) -> tuple[int, bytes]:
        path = urlsplit(url).path
        if path == "/api/ps":
            return 200, b'{"models": []}'
        if path == "/api/generate":
            return 200, b"{}"
        self.chat.append(payload)
        system = payload["messages"][0]["content"]
        role = next(r for r in ROLES if f"You are the {r}" in system)
        body = {"message": {"content": self.queues[role].pop(0)}, "done_reason": "stop",
                "prompt_eval_count": 1, "eval_count": 1}
        return 200, json.dumps(body).encode()


def factory_for(sim: OllamaSim):  # type: ignore[no-untyped-def]
    return lambda cfg: FreshLoadOllama(cfg, transport=sim)


def test_live_cell_runs_like_ppd(tmp_path: Path) -> None:
    sim = OllamaSim(2)
    runs = asyncio.run(run_live_cell(CELL, 2, factory=factory_for(sim), lock=tmp_path / "absent"))
    assert [e.ruling for e in runs[0].result.tool_events] == [Ruling.IN_MANDATE, Ruling.CANDIDATE, Ruling.CANDIDATE]
    assert [r.seed for r in runs] == [CELL.seed(0), CELL.seed(1)] and runs[0].seed != runs[1].seed
    assert [p["options"]["seed"] for p in sim.chat] == [runs[0].seed] * 6 + [runs[1].seed] * 6
    assert all(p["truncate"] is False and p["shift"] is False and p["think"] is False for p in sim.chat)
    assert all("temperature" not in p["options"] for p in sim.chat)
    assert all(r.unloads == 6 for r in runs) and len(runs[0].transcript) == 6


def test_live_cell_refuses_under_ppd_lock(tmp_path: Path) -> None:
    lock = tmp_path / "ppd.lock"
    lock.touch()
    sim = OllamaSim(1)
    with pytest.raises(GPUBusy):
        asyncio.run(run_live_cell(CELL, 1, factory=factory_for(sim), lock=lock))
    assert sim.chat == []


def test_live_compromised_a2_over_a2a(tmp_path: Path) -> None:
    sim = OllamaSim(1)
    cell = LiveCell("qwen3:14b", False, "compromised-worker", "A2")
    runs = asyncio.run(run_live_cell(cell, 1, transport="a2a", factory=factory_for(sim), lock=tmp_path / "absent"))
    assert [e.executed for e in runs[0].result.tool_events] == [False, False, False]


def test_live_rejects_empty_ensemble() -> None:
    with pytest.raises(ValueError):
        asyncio.run(run_live_cell(CELL, 0, guard=False, base=OllamaConfig()))


def test_cli_live_refused_under_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                     capsys: pytest.CaptureFixture[str]) -> None:
    lock = tmp_path / "ppd.lock"
    lock.touch()
    monkeypatch.setenv(LOCK_ENV, str(lock))
    assert main(["live", "--model", "qwen3:14b", "--n", "1"]) == 3
    assert "refused" in capsys.readouterr().err
