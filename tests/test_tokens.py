from __future__ import annotations

import base64
import json

import pytest

from hopscope.range.envelope import TaskEnvelope
from hopscope.range.levels import A2, get_level
from hopscope.range.tokens import TokenService
from hopscope.tools.caps import Mandate

KEY = b"k" * 32
M = Mandate.of("fs:read:/workspace/*")
ROOT = Mandate.of("fs:read:/workspace/*", "net:fetch:docs.example.com")


def test_roundtrip() -> None:
    ts = TokenService(KEY)
    assert ts.verify(ts.mint("r", 1, "planner", M), run_id="r", aud="planner") == M


@pytest.mark.parametrize(("run_id", "aud"), [("r", "worker"), ("other", "planner")])
def test_bound_to_run_and_receiver(run_id: str, aud: str) -> None:
    ts = TokenService(KEY)
    assert ts.verify(ts.mint("r", 1, "planner", M), run_id=run_id, aud=aud) is None


def test_other_key_and_tampering_rejected() -> None:
    tok = TokenService(KEY).mint("r", 1, "planner", M)
    assert TokenService(b"x" * 32).verify(tok, run_id="r", aud="planner") is None
    body = {"aud": "planner", "caps": ["secrets:get:*"], "hop": 1, "run": "r"}
    forged_b64 = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    forged = f"{forged_b64}.{tok.split('.')[1]}"
    assert TokenService(KEY).verify(forged, run_id="r", aud="planner") is None


@pytest.mark.parametrize("tok", [None, "", "a.b.c", "!!!.00", "abc"])
def test_garbage_rejected(tok: str | None) -> None:
    assert TokenService(KEY).verify(tok, run_id="r", aud="planner") is None


def test_short_key_rejected() -> None:
    with pytest.raises(ValueError):
        TokenService(b"short")


def test_a2_narrows_and_binds_receiver() -> None:
    lv = A2(TokenService(KEY))
    env = TaskEnvelope("r", 0, "user", "t", ROOT, token=lv.root_token("r", ROOT, "orchestrator"))
    assert lv.effective(env, "orchestrator") == ROOT and lv.effective(env, "planner") == Mandate()
    granted, tok = lv.delegate(env, "orchestrator", "planner", Mandate.of("fs:read:/workspace/*", "secrets:get:*"))
    assert granted == M
    assert lv.effective(env.child("orchestrator", "x", granted, tok), "planner") == M


def test_a2_ignores_forged_claim() -> None:
    lv = A2(TokenService(KEY))
    assert lv.effective(TaskEnvelope("r", 2, "worker", "t", Mandate.of("secrets:get:*")), "executor") == Mandate()
    assert isinstance(get_level("A2"), A2) and A2.enforce_tools is True
