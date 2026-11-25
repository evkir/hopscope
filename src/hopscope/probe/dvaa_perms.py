"""DVAA permission labels -> hopscope capabilities.

DVAA scenarios carry authority on the task as free-form labels (``permissions: ['read-only']``).
They are mapped onto the simulated vocabulary so a recorded edge can be measured with the
core ``Mandate.excess``. Tiers are never assigned here: they are derived by ``grammar.tier_of``
from ``tools.authority.GRANTS``. ``execute`` has no simulated tool and is reported
out-of-vocabulary with the ``exec`` label grammar.py uses for cards; unknown labels are kept
verbatim as unmapped, never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

from hopscope.probe.grammar import tier_of
from hopscope.tools.caps import Mandate

#: Concrete specs only: a wildcard action (``net:*:*``) is not covered by any grant, so it
#: would fall out of tier_of.
PERMISSION_CAPS: dict[str, tuple[str, ...]] = {
    "read-only": ("fs:read:/workspace/*",),
    "read-write": ("fs:read:/workspace/*", "fs:write:/workspace/*"),
    "network-access": ("net:fetch:*", "net:post:*"),
}

PERMISSION_OOV: dict[str, str] = {"execute": "exec"}


@dataclass(frozen=True, slots=True)
class PermissionReading:
    labels: tuple[str, ...]
    mandate: Mandate
    oov: tuple[str, ...]
    unmapped: tuple[str, ...]

    @property
    def tier(self) -> int | None:
        return max((t for c in self.mandate.caps if (t := tier_of(c)) is not None), default=None)


def read_permissions(labels: object) -> PermissionReading:
    """Read a DVAA ``permissions`` list; raise ValueError if it is not a list of strings."""
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
        raise ValueError("DVAA permissions must be a list of strings")
    norm = tuple(sorted({x.strip().lower() for x in labels if x.strip()}))
    specs = [s for x in norm for s in PERMISSION_CAPS.get(x, ())]
    oov = tuple(sorted({PERMISSION_OOV[x] for x in norm if x in PERMISSION_OOV}))
    unmapped = tuple(x for x in norm if x not in PERMISSION_CAPS and x not in PERMISSION_OOV)
    return PermissionReading(norm, Mandate.of(*specs), oov, unmapped)
