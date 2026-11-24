from __future__ import annotations

import asyncio
from collections import Counter

from hopscope.meter.matrix import collect
from hopscope.report.sarif import RULES, to_sarif
from hopscope.tools.authority import T1


def counts(sarif: dict) -> Counter:  # type: ignore[type-arg]
    return Counter(r["ruleId"] for r in sarif["runs"][0]["results"])


def test_structure() -> None:
    s = to_sarif(asyncio.run(collect(1)), version="9.9.9")
    assert s["version"] == "2.1.0" and s["$schema"].endswith("sarif-2.1.0.json")
    driver = s["runs"][0]["tool"]["driver"]
    assert driver["name"] == "hopscope" and driver["version"] == "9.9.9"
    ids = {r["id"] for r in RULES}
    for r in s["runs"][0]["results"]:
        assert r["ruleId"] in ids
        loc = r["locations"][0]["logicalLocations"][0]["fullyQualifiedName"]
        assert loc.count("/") == 3


def test_counts_over_the_matrix() -> None:
    assert counts(to_sarif(asyncio.run(collect(1)), version="x")) == {"HSC001": 8, "HSC002": 10, "HSC004": 5}


def test_t1_executor_yields_only_escalations_and_excess() -> None:
    assert counts(to_sarif(asyncio.run(collect(1, authority=T1)), version="x")) == {"HSC003": 18, "HSC004": 5}
