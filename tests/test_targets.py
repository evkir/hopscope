from __future__ import annotations

import pytest

from hopscope.targets import KNOWN_LOCAL_TARGETS, TargetRefused, check_target


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:7020/x", "http://localhost:7021/", "http://dvaa.test/", "http://[::1]:7020/", "http://a.localhost/"],
)
def test_local_targets_pass(url: str) -> None:
    check_target(url)


@pytest.mark.parametrize("url", ["https://example.com/", "http://10.0.0.5/", "http://192.168.1.10:7020/"])
def test_remote_targets_need_explicit_opt_in(url: str) -> None:
    with pytest.raises(TargetRefused):
        check_target(url)
    assert check_target(url, allow_remote=True)


@pytest.mark.parametrize("url", ["ftp://127.0.0.1/", "http:///nohost", "127.0.0.1:7020"])
def test_malformed_targets_refused(url: str) -> None:
    with pytest.raises(TargetRefused):
        check_target(url, allow_remote=True)


def test_known_targets_are_local() -> None:
    for t in KNOWN_LOCAL_TARGETS:
        check_target(t.card_url)
