"""Range agent: one LLM call per hop, then delegate downstream or execute tools."""

from __future__ import annotations

from typing import Any, Protocol

from hopscope.harness.llm_client import LLMBackend, LLMError
from hopscope.range.envelope import AgentResult, HopRecord, RunTrace, TaskEnvelope
from hopscope.range.levels import Level
from hopscope.range.roles import SCHEMAS, SYSTEM_PROMPTS, Role, render_user_message
from hopscope.tools.base import ToolCall, ToolError
from hopscope.tools.caps import Mandate
from hopscope.tools.gate import Gate
from hopscope.tools.registry import ToolRegistry


class Peer(Protocol):
    name: str

    async def handle(self, env: TaskEnvelope) -> AgentResult: ...


def parse_mandate(raw: Any) -> Mandate:
    if not isinstance(raw, list) or not all(isinstance(c, str) for c in raw):
        raise TypeError("capabilities must be a list of strings")
    return Mandate.of(*raw)


def parse_delegation(raw: Any) -> tuple[str, Mandate]:
    if not isinstance(raw, dict):
        raise TypeError("delegation must be an object")
    instruction = raw.get("instruction")
    if not isinstance(instruction, str) or not instruction:
        raise TypeError("instruction must be a non-empty string")
    return instruction, parse_mandate(raw.get("capabilities"))


class Agent:
    def __init__(
        self,
        name: str,
        role: Role,
        llm: LLMBackend,
        level: Level,
        trace: RunTrace,
        *,
        downstream: Peer | None = None,
        registry: ToolRegistry | None = None,
        gate: Gate | None = None,
    ) -> None:
        if role is Role.EXECUTOR:
            if registry is None or downstream is not None:
                raise ValueError("executor needs a registry and no downstream")
        elif downstream is None or registry is not None or gate is not None:
            raise ValueError(f"{role} needs a downstream peer and no registry or gate")
        self.name, self.role, self.llm, self.level, self.trace = name, role, llm, level, trace
        self.downstream, self.registry, self.gate = downstream, registry, gate

    async def handle(self, env: TaskEnvelope) -> AgentResult:
        try:
            out = self.llm.chat_json(
                [{"role": "user", "content": render_user_message(env)}],
                SCHEMAS[self.role],
                system=SYSTEM_PROMPTS[self.role],
                agent=self.name,
            )
        except LLMError as exc:
            return AgentResult(self.name, ok=False, errors=[str(exc)])
        if self.role is Role.EXECUTOR:
            return self._execute(env, out)
        return await self._delegate(env, out)

    async def _delegate(self, env: TaskEnvelope, out: dict[str, Any]) -> AgentResult:
        assert self.downstream is not None
        result = AgentResult(self.name, ok=True)
        steps = out.get("steps") if self.role is Role.PLANNER else [out]
        if not isinstance(steps, list):
            return AgentResult(self.name, ok=False, errors=["steps must be a list"])
        for raw in steps:
            try:
                instruction, requested = parse_delegation(raw)
            except (TypeError, ValueError) as exc:
                result.ok = False
                result.errors.append(f"bad delegation: {exc}")
                continue
            granted = self.level.grant(env.mandate, requested)
            child_env = env.child(self.name, instruction, granted)
            self.trace.hops.append(
                HopRecord(env.run_id, child_env.hop, self.name, self.downstream.name, env.mandate, requested, granted)
            )
            child = await self.downstream.handle(child_env)
            result.children.append(child)
            result.ok = result.ok and child.ok
        return result

    def _execute(self, env: TaskEnvelope, out: dict[str, Any]) -> AgentResult:
        assert self.registry is not None
        calls = out.get("tool_calls")
        if not isinstance(calls, list):
            return AgentResult(self.name, ok=False, errors=["tool_calls must be a list"])
        result = AgentResult(self.name, ok=True)
        for raw in calls:
            try:
                call = ToolCall(raw["tool"], raw["action"], dict(raw.get("args") or {}), caller=self.name)
                ev = self.registry.dispatch(call, env.mandate, enforce=self.level.enforce_tools, gate=self.gate)
            except (KeyError, TypeError, ValueError, ToolError) as exc:
                result.ok = False
                result.errors.append(f"bad tool call: {exc}")
                continue
            result.outputs.append({
                "seq": ev.seq,
                "executed": ev.executed,
                "ruling": ev.ruling.value if ev.ruling is not None else None,
                "result": ev.result,
                "error": ev.error,
            })
        return result
