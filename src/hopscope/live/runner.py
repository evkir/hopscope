"""Live ensembles on Ollama, run the way PPD v0.5 §5 runs its agents.

Every agent turn starts on a freshly loaded model, seeds come from the run's
coordinates (derive_seed, never 0), models run at their shipped sampling
parameters, and the server may neither truncate nor shift the context. CI drives
this through a simulated Ollama transport; it is never pointed at a real server
there. It refuses to start, and stops between runs, while the GPU is reserved for
PPD collection.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hopscope.harness.gpu_guard import check_gpu_free, check_lock
from hopscope.harness.llm_client import FreshLoadOllama, OllamaConfig
from hopscope.meter.ensemble import derive_seed
from hopscope.range.chain import RunResult, run_chain
from hopscope.range.demo import DEMO_INSTRUCTION, DEMO_ROOT
from hopscope.range.levels import get_level
from hopscope.range.scenarios import get_scenario
from hopscope.tools.authority import tier
from hopscope.tools.caps import Mandate

BackendFactory = Callable[[OllamaConfig], FreshLoadOllama]


@dataclass(frozen=True, slots=True)
class LiveCell:
    model: str
    think: bool | None
    scenario: str | None
    level: str
    authority: str = "T2"

    def seed(self, replicate: int) -> int:
        return derive_seed("live", self.model, self.think, self.scenario, self.level, self.authority, replicate)


@dataclass(frozen=True)
class LiveRun:
    result: RunResult
    seed: int
    transcript: tuple[dict[str, Any], ...]
    unloads: int


async def run_live_cell(
    cell: LiveCell,
    n: int,
    *,
    transport: str = "inproc",
    base: OllamaConfig | None = None,
    factory: BackendFactory | None = None,
    guard: bool = True,
    lock: Path | None = None,
) -> list[LiveRun]:
    if n < 1:
        raise ValueError(f"ensemble size must be >= 1, got {n}")
    config = base if base is not None else OllamaConfig(model=cell.model, think=cell.think)
    make: BackendFactory = factory if factory is not None else FreshLoadOllama
    if guard:
        check_gpu_free(make(config), lock=lock)
    sc = get_scenario(cell.scenario) if cell.scenario is not None else None
    authority = tier(int(cell.authority[1]))
    runs: list[LiveRun] = []
    llm: FreshLoadOllama | None = None
    try:
        for rep in range(n):
            if guard:
                check_lock(lock)
            seed = cell.seed(rep)
            llm = make(config.with_seed(seed))
            result = await run_chain(
                DEMO_INSTRUCTION,
                Mandate.of(*DEMO_ROOT),
                llm=llm,
                level=get_level(cell.level),
                run_id=f"live-{rep}",
                context=sc.context if sc else (),
                compromised=sc.compromised if sc else (),
                poisoned=sc.poisoned_cards if sc else (),
                transport=transport,
                authority=authority,
            )
            runs.append(LiveRun(result, seed, tuple(llm.transcript), llm.unloads))
    finally:
        if llm is not None:
            llm.unload()
    return runs
