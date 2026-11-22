"""Ensembles of runs. Seeds are derived from a run's coordinates, as in PPD v0.5 derive_seed.

Derived rather than drawn, so the seed list is fixed by the design and cannot be
chosen after a run has been seen; always in 1..2**31-1, because a backend may
read 0 as unset. Runs are sequential by design: one GPU, one model at a time.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Sequence

from hopscope.range.chain import RunResult

RunFactory = Callable[[int, int], Awaitable[RunResult]]


def derive_seed(*coords: object) -> int:
    material = "hopscope|" + "|".join(str(c) for c in coords)
    value = int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big")
    return value % (2**31 - 1) + 1


async def run_ensemble(
    n: int, factory: RunFactory, *, coords: Sequence[object] = (), start: int = 0
) -> list[RunResult]:
    """Call ``factory(replicate, seed)`` for replicates start..start+n-1, in order."""
    if n < 1:
        raise ValueError(f"ensemble size must be >= 1, got {n}")
    runs: list[RunResult] = []
    for rep in range(start, start + n):
        runs.append(await factory(rep, derive_seed(*coords, rep)))
    return runs
