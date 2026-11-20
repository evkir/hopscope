from __future__ import annotations

from hopscope.range.envelope import HopRecord, TaskEnvelope
from hopscope.tools.caps import Capability, Mandate

ROOT = Mandate.of("fs:read:/workspace/*")


def test_child_envelope() -> None:
    env = TaskEnvelope("r1", 0, "user", "task", ROOT, ("ctx",))
    child = env.child("orchestrator", "sub", Mandate())
    assert (child.run_id, child.hop, child.sender, child.context) == ("r1", 1, "orchestrator", ("ctx",))
    assert env.hop == 0


def test_hop_inflation() -> None:
    wider = Mandate.of("fs:read:/workspace/*", "secrets:get:*")
    rec = HopRecord("r1", 2, "planner", "worker", ROOT, wider, wider)
    assert rec.inflation == {Capability.parse("secrets:get:*")}
    assert not HopRecord("r1", 1, "a", "b", ROOT, ROOT, ROOT).inflation
