"""Sealed subprocess execution.

Vendored from CyberAI (MASec Lab), cyberai/core/sandbox/proc.py at commit
3da651806927b655c0ba2046e8b1f1aea03a4dda. Changes: hopscope logger name and HOME default; Docker and
toolchain helpers (operator_home, bridge_gateway_host) dropped.

If the child process inherits os.environ, the target reads our LLM API keys.
run_sealed() never inherits the parent environment. It constructs a minimal
env from a fixed base plus an explicit per-call allowlist, and refuses to pass
anything whose name looks like a credential.

This does not sandbox the filesystem or the network. It closes exactly one
door: environment-borne secret exfiltration. Containerisation covers the rest.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO, Any

_BASE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "TERM", "TZ")
_FALLBACK_PATH = "/usr/local/bin:/usr/bin:/bin"
DEFAULT_HOME = "/tmp/hopscope-worker-home"

logger = logging.getLogger("hopscope.harness.proc")

_SECRET_PATTERN = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWD|PASSWORD|CREDENTIAL|AUTH|SESSION|COOKIE|"
    r"PRIVATE|MNEMONIC|SEED)",
    re.IGNORECASE,
)


class SealedEnvError(RuntimeError):
    """Raised when a caller tries to leak a credential-looking variable."""


def sealed_env(
    allow: Sequence[str] | None = None,
    extra: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, str]:
    """Build a minimal environment for an untrusted child process."""
    env: dict[str, str] = {}
    for key in _BASE_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env.setdefault("PATH", _FALLBACK_PATH)

    for key in allow or ():
        if _SECRET_PATTERN.search(key):
            raise SealedEnvError(f"refusing to forward credential-shaped variable: {key}")
        value = os.environ.get(key)
        if value is not None:
            env[key] = value

    for key, value in (extra or {}).items():
        if _SECRET_PATTERN.search(key):
            raise SealedEnvError(f"refusing to inject credential-shaped variable: {key}")
        env[key] = str(value)

    env["HOME"] = str(home) if home else DEFAULT_HOME
    return env


def _check_argv(argv: Sequence[str]) -> list[str]:
    if isinstance(argv, (str, bytes)):
        raise SealedEnvError("argv must be a sequence, not a string")
    return list(argv)


def run_sealed(
    argv: Sequence[str],
    *,
    cwd: Path | str | None = None,
    timeout: float | None = None,
    allow: Sequence[str] | None = None,
    extra_env: Mapping[str, str] | None = None,
    home: Path | None = None,
    check: bool = False,
    stdin: int | IO[Any] | None = None,
) -> subprocess.CompletedProcess[str]:
    """subprocess.run() with a sealed environment. argv only, never a shell."""
    args = _check_argv(argv)
    env = sealed_env(allow=allow, extra=extra_env, home=home)
    return subprocess.run(  # noqa: S603 — argv list, no shell, sealed env
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
        stdin=stdin,
    )


def popen_sealed(
    argv: Sequence[str],
    *,
    cwd: Path | str | None = None,
    stdout: int | IO[Any] | None = None,
    stderr: int | IO[Any] | None = None,
    allow: Sequence[str] | None = None,
    extra_env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> subprocess.Popen[str]:
    """subprocess.Popen() with a sealed environment, for long-lived children."""
    args = _check_argv(argv)
    env = sealed_env(allow=allow, extra=extra_env, home=home)
    return subprocess.Popen(  # noqa: S603 — argv list, no shell, sealed env
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=stdout,
        stderr=stderr,
        text=True,
    )
