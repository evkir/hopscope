"""Tool registry: mandate check + append-only audit log (input for the MIR meter)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from hopscope.tools.base import SimTool, ToolCall, ToolError, ToolEvent
from hopscope.tools.caps import Mandate


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

    def dispatch(self, call: ToolCall, mandate: Mandate, *, enforce: bool) -> ToolEvent:
        """Run a call. With enforce=False (L0) unauthorized calls still execute but are logged."""
        tool = self.get(call.tool)
        required = tool.required(call)
        authorized = mandate.allows(required)
        result: Any = None
        error: str | None = None
        executed = False
        if enforce and not authorized:
            error = f"denied: {required}"
        else:
            try:
                result = tool.execute(call)
                executed = True
            except ToolError as exc:
                error = str(exc)
        event = ToolEvent(len(self.log), call, required, authorized, executed, result, error)
        self.log.append(event)
        return event
