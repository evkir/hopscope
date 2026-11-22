from __future__ import annotations

import json

from hopscope.range.envelope import TaskEnvelope
from hopscope.range.roles import (
    CHAIN,
    SCHEMAS,
    SYSTEM_PROMPTS,
    Role,
    next_role,
    render_user_message,
)
from hopscope.tools.caps import Mandate


def test_chain_and_next_role() -> None:
    assert [r.value for r in CHAIN] == ["orchestrator", "planner", "worker", "executor"]
    assert next_role(Role.PLANNER) is Role.WORKER and next_role(Role.EXECUTOR) is None


def test_every_role_has_schema_and_prompt() -> None:
    for role in Role:
        assert SCHEMAS[role]["type"] == "object" and "domain:action:resource" in SYSTEM_PROMPTS[role]


def test_render_is_deterministic_and_sorted() -> None:
    env = TaskEnvelope("r", 0, "user", "do", Mandate.of("net:fetch:a", "fs:read:b"), ("page",))
    msg = render_user_message(env)
    assert msg == render_user_message(env)
    assert json.loads(msg) == {"instruction": "do", "mandate": ["fs:read:b", "net:fetch:a"], "context": ["page"]}
