from __future__ import annotations

import asyncio

import pytest

from hopscope.meter.metrics import (
    RunMetrics,
    ensemble_metrics,
    format_ensemble,
    run_metrics,
    wilson,
)
from hopscope.range.demo import run_demo
from hopscope.tools.authority import T1


def rm(valid: bool = True, c: int = 0, e: int = 0) -> RunMetrics:
    return RunMetrics("r", valid, 1, c, e, 0, 0, 5)


def test_run_metrics_demo() -> None:
    m = run_metrics(asyncio.run(run_demo()))
    assert (m.valid, m.in_mandate, m.candidates, m.escalations, m.unruled) == (True, 1, 2, 0, 0)
    assert (m.excess_hops, m.delegations) == (1, 5)


def test_run_metrics_t1() -> None:
    m = run_metrics(asyncio.run(run_demo(authority=T1)))
    assert (m.candidates, m.escalations) == (0, 2)


def test_wilson_known_values() -> None:
    assert wilson(5, 10) == pytest.approx((0.2366, 0.7634), abs=1e-4)
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == pytest.approx(1.0)


@pytest.mark.parametrize(("k", "n"), [(0, 0), (3, 2), (-1, 5)])
def test_wilson_rejects(k: int, n: int) -> None:
    with pytest.raises(ValueError):
        wilson(k, n)


def test_ensemble_excludes_invalid_runs() -> None:
    m = ensemble_metrics([rm(c=1), rm(c=2, e=1), rm(), rm(valid=False, c=9)])
    assert (m.n_runs, m.n_valid) == (4, 3)
    assert m.cir == pytest.approx(2 / 3) and m.esr == pytest.approx(1 / 3)


def test_ensemble_without_valid_runs() -> None:
    m = ensemble_metrics([rm(valid=False)])
    assert m.cir is None and m.esr is None
    assert "CIR=n/a" in format_ensemble(m)


def test_format_states_not_mir() -> None:
    out = format_ensemble(ensemble_metrics([rm(c=1)]))
    assert out.startswith("runs=1 valid=1 CIR=1.000") and out.endswith("(D7(i)-(ii) only; not MIR)")
