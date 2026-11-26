"""Drive a recorded chain lab once and read the hop it taps.

One POST to the lab's entry point, then the hop's ingress/egress records are read back. Only
tasks absent from the records before the POST are read, so earlier runs in the same ``out/``
never leak into this reading. The record directory is ground truth and is never truncated.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from hopscope.probe.chain import EdgeReading, _task_id, pair_records, read_edge, read_records
from hopscope.targets import check_target

DEFAULT_PAYLOAD: dict[str, Any] = {"quarter": "Q1"}


class ChainError(RuntimeError):
    """The chain lab answered badly or recorded no complete new hop."""


def _bodies(path: Path) -> list[dict]:
    return read_records(path) if path.exists() else []


def probe_chain(
    url: str,
    hop: str,
    records: Path,
    *,
    allow_remote: bool = False,
    payload: dict[str, Any] | None = None,
    transport: Any = None,
    timeout: float = 30.0,
    wait: float = 5.0,
    poll: float = 0.1,
) -> list[EdgeReading]:
    check_target(url, allow_remote=allow_remote)
    inbound, outbound = records / f"{hop}.in.jsonl", records / f"{hop}.out.jsonl"
    seen = {_task_id(b) for b in _bodies(inbound) + _bodies(outbound)}
    with httpx.Client(transport=transport, follow_redirects=False, trust_env=False, timeout=timeout) as client:
        resp = client.post(url, json=DEFAULT_PAYLOAD if payload is None else payload)
    if not resp.is_success:
        raise ChainError(f"{url} answered HTTP {resp.status_code}")
    deadline = time.monotonic() + wait
    while True:
        fresh_in = [b for b in _bodies(inbound) if _task_id(b) not in seen]
        fresh_out = [b for b in _bodies(outbound) if _task_id(b) not in seen]
        pairs, unmatched = pair_records(fresh_in, fresh_out)
        if pairs and not unmatched:
            return [read_edge(hop, i, o) for i, o in pairs]
        if time.monotonic() >= deadline:
            raise ChainError(f"{hop}: unmatched after POST ({', '.join(unmatched) or 'no new records'})")
        time.sleep(poll)
