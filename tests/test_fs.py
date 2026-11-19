from __future__ import annotations

import pytest

from hopscope.tools.base import ToolCall, ToolError
from hopscope.tools.caps import Capability, Mandate
from hopscope.tools.fs import SimFS, norm_path


def fs() -> SimFS:
    return SimFS({"/workspace/a.txt": "A", "/etc/shadow": "S"})


@pytest.mark.parametrize(
    ("raw", "want"),
    [("/workspace/../etc/shadow", "/etc/shadow"), ("//etc", "/etc"), ("/w/./x", "/w/x"), ("/", "/")],
)
def test_norm_path(raw: str, want: str) -> None:
    assert norm_path(raw) == want


def test_relative_path_rejected() -> None:
    with pytest.raises(ToolError):
        norm_path("workspace/a.txt")


def test_traversal_cannot_bypass_glob() -> None:
    req = fs().required(ToolCall("fs", "read", {"path": "/workspace/../etc/shadow"}))
    assert req == Capability.parse("fs:read:/etc/shadow")
    assert not Mandate.of("fs:read:/workspace/*").allows(req)


def test_read_write_list_delete() -> None:
    f = fs()
    assert f.execute(ToolCall("fs", "read", {"path": "/workspace/a.txt"})) == "A"
    assert f.execute(ToolCall("fs", "write", {"path": "/workspace/b.txt", "content": "BB"})) == 2
    assert f.execute(ToolCall("fs", "list", {"path": "/workspace"})) == ["/workspace/a.txt", "/workspace/b.txt"]
    assert f.execute(ToolCall("fs", "delete", {"path": "/workspace/a.txt"})) is True
    with pytest.raises(ToolError):
        f.execute(ToolCall("fs", "read", {"path": "/workspace/a.txt"}))
