"""Tool registry: capability gate, mandate check and append-only audit log (input for the meter)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from hopscope.tools.base import SimTool, ToolCall, ToolError, ToolEvent
from hopscope.tools.caps import Mandate
from hopscope.tools.gate import Gate, Ruling


class ToolRegistry:
    def __init__(self, tools: Iterable[SimTool]) -> None:
        self._tools: dict[str, SimTool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"duplicate tool {tool.name!r}")
            self._tools[tool.name] = tool
        self.log: list[ToolEvent] = []

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def get(self, name: str) -> SimTool:
        try:
            return self._tools[name]
        except KeyError:
            raise ToolError(f"unknown tool {name!r}") from None

    def dispatch(
        self,
        call: ToolCall,
        mandate: Mandate,
        *,
        enforce: bool,
        gate: Gate | None = None,
    ) -> ToolEvent:
        """Run one call and log it.

        ``mandate`` is what was delegated to the caller; ``enforce`` makes it binding
        (A1/A2). With a ``gate``, an invocation outside the caller's own C(A) is an
        escalation and is never executed at any level (PPD v0.5 §5: blocked
        invocations are logged, not executed). Every denial gets the same answer,
        whichever boundary was crossed.
        """
        tool = self.get(call.tool)
        required = tool.required(call)
        authorized = mandate.allows(required)
        ruling = gate.rule(required) if gate is not None else None
        result: Any = None
        error: str | None = None
        executed = False
        if ruling is Ruling.ESCALATION or (enforce and not authorized):
            error = f"denied: {required}"
        else:
            try:
                result = tool.execute(call)
                executed = True
            except ToolError as exc:
                error = str(exc)
        event = ToolEvent(len(self.log), call, required, authorized, executed, result, error, ruling)
        self.log.append(event)
        return event
