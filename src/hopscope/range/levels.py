"""Attenuation levels. A level decides what a child actually receives on delegation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from hopscope.tools.caps import Mandate


class Level(ABC):
    name: ClassVar[str]
    enforce_tools: ClassVar[bool]

    @abstractmethod
    def grant(self, held: Mandate, requested: Mandate) -> Mandate: ...


class L0(Level):
    """No attenuation: the child gets whatever its parent asks for; tools are not enforced."""

    name = "L0"
    enforce_tools = False

    def grant(self, held: Mandate, requested: Mandate) -> Mandate:
        return requested


LEVELS: dict[str, type[Level]] = {"L0": L0}


def get_level(name: str) -> Level:
    try:
        return LEVELS[name]()
    except KeyError:
        raise ValueError(f"unknown level {name!r}; known: {sorted(LEVELS)}") from None
