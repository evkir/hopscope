from __future__ import annotations

import asyncio

from hopscope.meter.exploratory import excess_by_depth, lambda_exc, mean_lambda_exc
from hopscope.range.demo import run_demo


def test_lambda_exc_by_level() -> None:
    assert lambda_exc(asyncio.run(run_demo())) == 0.2
    assert lambda_exc(asyncio.run(run_demo(level="A1"))) == 0.0
    assert lambda_exc(asyncio.run(run_demo(level="A2"))) == 0.0


def test_forgery_is_recorded_even_when_blocked() -> None:
    run = asyncio.run(run_demo(level="A2", scenario="compromised-worker"))
    assert lambda_exc(run) == 0.2
    assert excess_by_depth([run]) == {1: 0.0, 2: 0.0, 3: 0.5}


def test_excess_by_depth_and_mean() -> None:
    runs = [asyncio.run(run_demo()), asyncio.run(run_demo(level="A1"))]
    assert excess_by_depth(runs[:1]) == {1: 0.0, 2: 0.5, 3: 0.0}
    assert mean_lambda_exc(runs) == 0.1 and mean_lambda_exc([]) is None


def test_levenshtein_and_normalisation() -> None:
    from hopscope.meter.exploratory import levenshtein, normalized_distance

    assert levenshtein("kitten", "sitting") == 3
    assert normalized_distance((), ()) == 0.0
    assert normalized_distance(("a", "b"), ("a", "c")) == 0.5


def test_mean_pairwise() -> None:
    from hopscope.meter.exploratory import mean_pairwise

    assert mean_pairwise([("a", "b"), ("a", "b"), ("a", "c")]) == (0.0 + 0.5 + 0.5) / 3
    assert mean_pairwise([("a",)]) is None


def test_lambda_div_is_zero_for_deterministic_replicates() -> None:
    from hopscope.meter.exploratory import lambda_div, trajectory
    from hopscope.range.demo import run_demo_ensemble

    runs = asyncio.run(run_demo_ensemble(3))
    assert lambda_div(runs) == 0.0
    assert trajectory(runs[0])[1] == "secrets:get:api_key"
