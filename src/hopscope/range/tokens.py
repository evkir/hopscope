"""Delegation tokens for A2: HMAC-SHA256 over a canonical body, bound to run and receiver.

The issuer is outside the agents: an agent can ask for a narrower token but cannot mint one,
so a compromised hop can forge the metadata claim and replay its own token, never widen it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets

from hopscope.tools.caps import Mandate

MIN_KEY_BYTES = 32


class TokenService:
    def __init__(self, key: bytes | None = None) -> None:
        key = key if key is not None else secrets.token_bytes(MIN_KEY_BYTES)
        if len(key) < MIN_KEY_BYTES:
            raise ValueError(f"token key must be at least {MIN_KEY_BYTES} bytes")
        self._key = key

    def _sign(self, body_b64: str) -> str:
        return hmac.new(self._key, body_b64.encode(), hashlib.sha256).hexdigest()

    def mint(self, run_id: str, hop: int, aud: str, mandate: Mandate) -> str:
        body = json.dumps(
            {"run": run_id, "hop": hop, "aud": aud, "caps": list(mandate.specs())},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        b64 = base64.urlsafe_b64encode(body).decode().rstrip("=")
        return f"{b64}.{self._sign(b64)}"

    def verify(self, token: str | None, *, run_id: str, aud: str) -> Mandate | None:
        """The mandate a valid token grants ``aud`` in ``run_id``; None for anything else."""
        if not token or token.count(".") != 1:
            return None
        b64, sig = token.split(".")
        if not hmac.compare_digest(sig, self._sign(b64)):
            return None
        try:
            body = json.loads(base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)))
        except ValueError:
            return None
        if not isinstance(body, dict) or body.get("run") != run_id or body.get("aud") != aud:
            return None
        caps = body.get("caps")
        if not isinstance(caps, list) or not all(isinstance(c, str) for c in caps):
            return None
        try:
            return Mandate.of(*caps)
        except ValueError:
            return None
