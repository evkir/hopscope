from __future__ import annotations

import pytest

from hopscope.tools.caps import Capability, Domain, Mandate


def test_parse_roundtrip() -> None:
    c = Capability.parse("fs:read:/workspace/*")
    assert c == Capability(Domain.FS, "read", "/workspace/*")
    assert str(c) == "fs:read:/workspace/*"


def test_parse_keeps_colons_in_resource() -> None:
    assert Capability.parse("net:fetch:host:8080").resource == "host:8080"


@pytest.mark.parametrize("bad", ["fs:read", "bogus:read:*", "fs::x", "fs:read:"])
def test_parse_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        Capability.parse(bad)


def test_covers_glob_action_domain() -> None:
    c = Capability.parse("fs:read:/workspace/*")
    assert c.covers(Capability.parse("fs:read:/workspace/a/b.txt"))
    assert not c.covers(Capability.parse("fs:read:/etc/passwd"))
    assert not c.covers(Capability.parse("fs:write:/workspace/a"))
    assert not c.covers(Capability.parse("secrets:read:/workspace/a"))


def test_wildcard_request_not_covered_by_narrow_grant() -> None:
    assert not Capability.parse("fs:read:/workspace/*").covers(Capability.parse("fs:read:*"))


def test_mandate_allows() -> None:
    m = Mandate.of("fs:read:/workspace/*", "net:fetch:docs.example.com")
    assert m.allows(Capability.parse("net:fetch:docs.example.com"))
    assert not m.allows(Capability.parse("net:post:docs.example.com"))
    assert not Mandate().allows(Capability.parse("fs:read:/x"))


def test_mandate_str_is_sorted() -> None:
    assert str(Mandate.of("net:fetch:a", "fs:read:b")) == "fs:read:b, net:fetch:a"


def test_mandate_excess_and_covers() -> None:
    held = Mandate.of("fs:read:/workspace/*", "net:fetch:docs.example.com")
    narrower = Mandate.of("fs:read:/workspace/a.txt")
    wider = Mandate.of("fs:read:/workspace/*", "secrets:get:*")
    assert held.covers(narrower) and held.excess(narrower) == frozenset()
    assert held.excess(wider) == {Capability.parse("secrets:get:*")}
    assert not held.covers(wider)
    assert Mandate().covers(Mandate())


def test_mandate_specs_sorted() -> None:
    assert Mandate.of("net:fetch:a", "fs:read:b").specs() == ("fs:read:b", "net:fetch:a")
