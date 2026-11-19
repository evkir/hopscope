from __future__ import annotations

import ast
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

import hopscope.tools

FORBIDDEN = ("socket", "ssl", "http", "urllib.request", "requests", "httpx", "aiohttp")
TOOLS_DIR = Path(hopscope.tools.__file__).parent


def _imports(path: Path) -> Iterator[str]:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
            yield from (f"{node.module}.{a.name}" for a in node.names)


def test_runtime_guard_blocks_sockets() -> None:
    with pytest.raises(RuntimeError, match="forbidden"):
        socket.create_connection(("127.0.0.1", 9))


@pytest.mark.parametrize("path", sorted(TOOLS_DIR.glob("*.py")), ids=lambda p: p.name)
def test_tools_do_not_import_network_modules(path: Path) -> None:
    bad = [m for m in _imports(path) if any(m == f or m.startswith(f + ".") for f in FORBIDDEN)]
    assert not bad, f"{path.name} imports {bad}"
