"""Attenuation levels A0-A2: what a child actually receives on delegation.

Not to be confused with the authority levels L0-L2 of the PPD pre-registration
(10.5281/zenodo.23513214), which are fixed tool allowlists of agents.

A0  none: the child gets what its parent asks for; the delegated mandate does not bind tools.
A1  scope: the child gets requested ∩ held and the delegated mandate binds tools. The mandate
    still travels as an unauthenticated claim, so a hop that does not attenuate defeats it.
A2  token exchange: as A1, but the mandate travels as a token minted by an issuer outside the
    agents; a receiver acts only on what a valid token addressed to it grants.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from hopscope.range.envelope import TaskEnvelope
from hopscope.tools.caps import Mandate


def attenuate(held: Mandate, requested: Mandate) -> Mandate:
    """Every requested capability that some held capability covers; the rest is dropped."""
    return Mandate(frozenset(c for c in requested.caps if held.allows(c)))


class Level(ABC):
    name: ClassVar[str]
    enforce_tools: ClassVar[bool]

    @abstractmethod
    def grant(self, held: Mandate, requested: Mandate) -> Mandate: ...

    def root_token(self, run_id: str, root: Mandate, receiver: str) -> str | None:
        return None

    def effective(self, env: TaskEnvelope, me: str) -> Mandate:
        """The mandate ``me`` acts under on receiving ``env``."""
        return env.mandate

    def delegate(
        self, env: TaskEnvelope, sender: str, receiver: str, requested: Mandate
    ) -> tuple[Mandate, str | None]:
        return self.grant(self.effective(env, sender), requested), None


class A0(Level):
    name = "A0"
    enforce_tools = False

    def grant(self, held: Mandate, requested: Mandate) -> Mandate:
        return requested


class A1(Level):
    name = "A1"
    enforce_tools = True

    def grant(self, held: Mandate, requested: Mandate) -> Mandate:
        return attenuate(held, requested)


LEVELS: dict[str, type[Level]] = {"A0": A0, "A1": A1}


def get_level(name: str) -> Level:
    try:
        return LEVELS[name]()
    except KeyError:
        raise ValueError(f"unknown level {name!r}; known: {sorted(LEVELS)}") from None
