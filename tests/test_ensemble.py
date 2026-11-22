from __future__ import annotations

import asyncio

import pytest

from hopscope.cli import main
from hopscope.meter.ensemble import derive_seed, run_ensemble
from hopscope.range.chain import RunResult
from hopscope.range.demo import run_demo


def test_derive_seed_stable_positive_distinct() -> None:
    s = derive_seed("demo", "A0", 0)
    assert s == derive_seed("demo", "A0", 0) and 1 <= s < 2**31
    assert s != derive_seed("demo", "A0", 1)


def test_run_ensemble_replicates_and_seeds_in_order() -> None:
    seen: list[tuple[int, int]] = []

    async def factory(rep: int, seed: int) -> RunResult:
        seen.append((rep, seed))
        return await run_demo(run_id=f"demo-{rep}")

    runs = asyncio.run(run_ensemble(3, factory, coords=("demo", "A0")))
    assert [r.run_id for r in runs] == ["demo-0", "demo-1", "demo-2"]
    assert seen == [(i, derive_seed("demo", "A0", i)) for i in range(3)]


def test_run_ensemble_rejects_empty() -> None:
    async def factory(rep: int, seed: int) -> RunResult:
        raise AssertionError("must not be called")

    with pytest.raises(ValueError):
        asyncio.run(run_ensemble(0, factory))


def test_cli_run_t2_and_t1(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--n", "5"]) == 0
    out = capsys.readouterr().out
    assert "runs=5 valid=5 CIR=1.000" in out and "ESR=0.000" in out and "not MIR" in out
    assert main(["run", "--n", "3", "--authority", "T1", "--transport", "a2a"]) == 0
    out = capsys.readouterr().out
    assert "CIR=0.000" in out and "ESR=1.000" in out


def test_cli_run_rejects_zero() -> None:
    with pytest.raises(SystemExit):
        main(["run", "--n", "0"])
