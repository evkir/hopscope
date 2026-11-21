"""Wire codec: TaskEnvelope <-> a2a Message, AgentResult <-> JSON text.

At A0 the mandate travels as an unauthenticated claim in message metadata and
the receiver trusts it. That is the weakness hopscope measures; A2 replaces the
claim with an exchanged token.
"""

from __future__ import annotations

import json
from typing import Any

from a2a.helpers import get_message_text, new_text_message
from a2a.types import Message, Role
from google.protobuf.json_format import MessageToDict

from hopscope.range.envelope import AgentResult, TaskEnvelope
from hopscope.tools.caps import Mandate

MANDATE_EXT = "https://maseclab.com/ext/hopscope/mandate/v0.1"
META_KEY = "hopscope"
ROLE_USER = Role.Value("ROLE_USER")
ROLE_AGENT = Role.Value("ROLE_AGENT")
MAX_RESULT_BYTES = 1_000_000


class CodecError(ValueError):
    """Malformed hopscope payload on the wire."""


def _str_list(raw: Any, what: str) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise CodecError(f"{what} must be a list of strings")
    return raw


def envelope_to_message(env: TaskEnvelope) -> Message:
    msg = new_text_message(env.instruction, role=ROLE_USER)
    msg.metadata.update({
        META_KEY: {
            "run_id": env.run_id,
            "hop": env.hop,
            "sender": env.sender,
            "mandate": list(env.mandate.specs()),
            "context": list(env.context),
        }
    })
    msg.extensions.append(MANDATE_EXT)
    return msg


def message_to_envelope(msg: Message) -> TaskEnvelope:
    meta = MessageToDict(msg.metadata).get(META_KEY)
    if not isinstance(meta, dict):
        raise CodecError("missing hopscope metadata")
    run_id, sender, hop = meta.get("run_id"), meta.get("sender"), meta.get("hop")
    if not isinstance(run_id, str) or not run_id or not isinstance(sender, str) or not sender:
        raise CodecError("run_id and sender must be non-empty strings")
    if isinstance(hop, bool) or not isinstance(hop, (int, float)) or hop < 0 or hop != int(hop):
        raise CodecError("hop must be a non-negative integer")
    instruction = get_message_text(msg)
    if not instruction:
        raise CodecError("empty instruction")
    try:
        mandate = Mandate.of(*_str_list(meta.get("mandate"), "mandate"))
    except ValueError as exc:
        raise CodecError(f"bad mandate: {exc}") from exc
    context = tuple(_str_list(meta.get("context", []), "context"))
    return TaskEnvelope(run_id, int(hop), sender, instruction, mandate, context)


def _r2d(r: AgentResult) -> dict[str, Any]:
    return {
        "agent": r.agent,
        "ok": r.ok,
        "outputs": r.outputs,
        "errors": r.errors,
        "children": [_r2d(c) for c in r.children],
    }


def _d2r(d: Any) -> AgentResult:
    if not isinstance(d, dict):
        raise CodecError("result must be an object")
    agent, ok = d.get("agent"), d.get("ok")
    outputs, errors, children = d.get("outputs", []), d.get("errors", []), d.get("children", [])
    if not isinstance(agent, str) or not isinstance(ok, bool) or not isinstance(outputs, list) \
            or not isinstance(children, list):
        raise CodecError("malformed result")
    return AgentResult(agent, ok, outputs, _str_list(errors, "errors"), [_d2r(c) for c in children])


def result_to_text(r: AgentResult) -> str:
    return json.dumps(_r2d(r), sort_keys=True, default=str)


def result_from_text(text: str) -> AgentResult:
    if len(text.encode()) > MAX_RESULT_BYTES:
        raise CodecError("result too large")
    try:
        return _d2r(json.loads(text))
    except (json.JSONDecodeError, RecursionError) as exc:
        raise CodecError(f"result is not valid JSON: {type(exc).__name__}") from exc


def reply_message(r: AgentResult, context_id: str | None) -> Message:
    return new_text_message(result_to_text(r), role=ROLE_AGENT, context_id=context_id)
