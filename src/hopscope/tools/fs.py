"""Simulated filesystem (in-memory). Paths are normalized before the capability check."""

from __future__ import annotations

import posixpath
from collections.abc import Mapping
from typing import Any

from hopscope.tools.base import SimTool, ToolCall, ToolError, get_arg
from hopscope.tools.caps import Domain


def norm_path(path: str) -> str:
    if not path.startswith("/"):
        raise ToolError(f"fs: path must be absolute, got {path!r}")
    p = posixpath.normpath(path)
    return "/" + p.lstrip("/")  # POSIX keeps a leading '//'; collapse it


class SimFS(SimTool):
    name = "fs"
    domain = Domain.FS
    actions = frozenset({"read", "write", "list", "delete"})

    def __init__(self, files: Mapping[str, str] | None = None) -> None:
        self.files: dict[str, str] = {norm_path(p): c for p, c in (files or {}).items()}

    def resource(self, call: ToolCall) -> str:
        return norm_path(get_arg(call, "path"))

    def execute(self, call: ToolCall) -> Any:
        path = self.resource(call)
        match call.action:
            case "read":
                if path not in self.files:
                    raise ToolError(f"fs: no such file {path!r}")
                return self.files[path]
            case "write":
                content = get_arg(call, "content")
                self.files[path] = content
                return len(content)
            case "list":
                prefix = path.rstrip("/") + "/"
                return sorted(p for p in self.files if p.startswith(prefix))
            case "delete":
                if self.files.pop(path, None) is None:
                    raise ToolError(f"fs: no such file {path!r}")
                return True
        raise ToolError(f"fs: unhandled action {call.action!r}")
