"""Attenuation levels A0-A2: what a child actually receives on delegation.

Not to be confused with the authority levels L0-L2 of the PPD pre-registration
(10.5281/zenodo.23513214), which are fixed tool allowlists of agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from hopscope.tools.caps import Mandate


class Level(ABC):
    name: ClassVar[str]
    enforce_tools: ClassVar[bool]

    @abstractmethod
    def grant(self, held: Mandate, requested: Mandate) -> Mandate: ...


class A0(Level):
    """No attenuation: the child gets whatever its parent asks for; tools are not enforced."""

    name = "A0"
    enforce_tools = False

    def grant(self, held: Mandate, requested: Mandate) -> Mandate:
        return requested


LEVELS: dict[str, type[Level]] = {"A0": A0}


def get_level(name: str) -> Level:
    try:
        return LEVELS[name]()
    except KeyError:
        raise ValueError(f"unknown level {name!r}; known: {sorted(LEVELS)}") from None
