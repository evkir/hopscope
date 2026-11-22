"""Simulated tool contract: declare the capability a call needs, execute in memory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from hopscope.tools.caps import Capability, Domain
from hopscope.tools.gate import Ruling


class ToolError(Exception):
    """Invalid call: unknown tool/action, bad arguments, or simulated failure."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    tool: str
    action: str
    args: Mapping[str, Any] = field(default_factory=dict)
    caller: str = "unknown"


@dataclass(frozen=True, slots=True)
class ToolEvent:
    seq: int
    call: ToolCall
    required: Capability
    authorized: bool
    executed: bool
    result: Any = None
    error: str | None = None
    ruling: Ruling | None = None


def get_arg(call: ToolCall, key: str, typ: type = str) -> Any:
    value = call.args.get(key)
    if type(value) is not typ or (typ is str and not value):
        raise ToolError(f"{call.tool}.{call.action}: arg {key!r} must be non-empty {typ.__name__}")
    return value


class SimTool(ABC):
    name: ClassVar[str]
    domain: ClassVar[Domain]
    actions: ClassVar[frozenset[str]]

    def required(self, call: ToolCall) -> Capability:
        if call.action not in self.actions:
            raise ToolError(f"{self.name}: unknown action {call.action!r}")
        return Capability(self.domain, call.action, self.resource(call))

    @abstractmethod
    def resource(self, call: ToolCall) -> str: ...

    @abstractmethod
    def execute(self, call: ToolCall) -> Any: ...
