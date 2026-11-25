"""Read a recorded delegation hop: what the hop received (ingress) vs what it handed on (egress).

Input is a pair of task bodies observed on the wire by labs/dvaa-chain (tap before the hop, sink
after it). Excess is the core ``Mandate.excess`` with the range's orientation,
``held.excess(granted)``: capabilities handed on that the hop itself was never given. Context
text is never kept, only its length and a short sha256, so a report cannot carry injected
instructions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from hopscope.probe.dvaa_perms import PermissionReading, read_permissions
from hopscope.tools.caps import Capability

MAX_RECORD_BYTES = 4 << 20


@dataclass(frozen=True, slots=True)
class TextDigest:
    length: int
    sha256: str

    @classmethod
    def of(cls, text: object) -> TextDigest:
        s = text if isinstance(text, str) else ""
        return cls(len(s), hashlib.sha256(s.encode("utf-8")).hexdigest()[:16])


@dataclass(frozen=True, slots=True)
class EdgeReading:
    hop: str
    task_id: str
    held: PermissionReading
    granted: PermissionReading
    excess: frozenset[Capability]
    oov_added: tuple[str, ...]
    origin_rewritten: bool
    context_appended: bool
    context_rewritten: bool
    hidden_fields: tuple[str, ...]
    context_in: TextDigest
    context_out: TextDigest

    @property
    def escalated(self) -> bool:
        return bool(self.excess or self.oov_added)

    @property
    def poisoned(self) -> bool:
        return (
            self.escalated
            or self.origin_rewritten
            or self.context_appended
            or self.context_rewritten
            or bool(self.hidden_fields)
        )


def _task_id(body: dict) -> str:
    return str(body.get("id"))


def read_edge(hop: str, inbound: object, outbound: object) -> EdgeReading:
    """Compare one task as it entered ``hop`` with the same task as ``hop`` forwarded it."""
    if not isinstance(inbound, dict) or not isinstance(outbound, dict):
        raise ValueError("edge bodies must be JSON objects")
    tid_in, tid_out = _task_id(inbound), _task_id(outbound)
    if tid_in != tid_out:
        raise ValueError(f"edge pairs different tasks: {tid_in!r} != {tid_out!r}")
    held = read_permissions(inbound.get("permissions", []))
    granted = read_permissions(outbound.get("permissions", []))
    ctx_in, ctx_out = inbound.get("context"), outbound.get("context")
    s_in = ctx_in if isinstance(ctx_in, str) else ""
    s_out = ctx_out if isinstance(ctx_out, str) else ""
    appended = s_out != s_in and s_out.startswith(s_in)
    return EdgeReading(
        hop=hop,
        task_id=tid_in,
        held=held,
        granted=granted,
        excess=held.mandate.excess(granted.mandate),
        oov_added=tuple(sorted(set(granted.oov) - set(held.oov))),
        origin_rewritten=inbound.get("from") != outbound.get("from"),
        context_appended=appended,
        context_rewritten=s_out != s_in and not appended,
        hidden_fields=tuple(sorted(k for k in outbound if k.startswith("_") and k not in inbound)),
        context_in=TextDigest.of(ctx_in),
        context_out=TextDigest.of(ctx_out),
    )


def read_records(path: Path, *, max_bytes: int = MAX_RECORD_BYTES) -> list[dict]:
    """Task bodies of ``POST /tasks/send`` entries in a recorder JSONL file."""
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ValueError(f"{path.name}: {len(data)} bytes exceeds {max_bytes}")
    bodies: list[dict] = []
    for n, line in enumerate(data.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path.name}:{n}: bad json") from e
        if isinstance(entry, dict) and entry.get("path") == "/tasks/send" and isinstance(entry.get("body"), dict):
            bodies.append(entry["body"])
    return bodies


def pair_records(inbound: list[dict], outbound: list[dict]) -> tuple[list[tuple[dict, dict]], tuple[str, ...]]:
    """Pair ingress/egress bodies by task id; report what did not pair as ``in:<id>``/``out:<id>``."""
    by_id: dict[str, dict] = {}
    for body in outbound:
        by_id.setdefault(_task_id(body), body)
    pairs: list[tuple[dict, dict]] = []
    unmatched: list[str] = []
    for body in inbound:
        tid = _task_id(body)
        if tid in by_id:
            pairs.append((body, by_id.pop(tid)))
        else:
            unmatched.append(f"in:{tid}")
    unmatched += [f"out:{tid}" for tid in by_id]
    return pairs, tuple(unmatched)
