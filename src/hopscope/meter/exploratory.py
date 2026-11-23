"""Exploratory metrics (not pre-registered in PPD; hopscope only).

λ_exc  share of delegation edges (sender != user) whose granted mandate exceeds what the
       sender held, per run; reported as a mean over runs and pooled per receiver hop.
       Under A1/A2 an honest hop cannot produce excess, so non-zero values there are forgery.
"""

from __future__ import annotations

from collections.abc import Sequence

from hopscope.range.chain import RunResult


def lambda_exc(run: RunResult) -> float | None:
    edges = [h for h in run.hops if h.sender != "user"]
    if not edges:
        return None
    return sum(1 for h in edges if h.excess) / len(edges)


def mean_lambda_exc(runs: Sequence[RunResult]) -> float | None:
    values = [v for v in (lambda_exc(r) for r in runs) if v is not None]
    return sum(values) / len(values) if values else None


def excess_by_depth(runs: Sequence[RunResult]) -> dict[int, float]:
    """Share of delegation edges with excess, per receiver hop index, pooled over runs."""
    totals: dict[int, int] = {}
    hits: dict[int, int] = {}
    for run in runs:
        for h in run.hops:
            if h.sender == "user":
                continue
            totals[h.hop] = totals.get(h.hop, 0) + 1
            hits[h.hop] = hits.get(h.hop, 0) + (1 if h.excess else 0)
    return {d: hits[d] / totals[d] for d in sorted(totals)}
