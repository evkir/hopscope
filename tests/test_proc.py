from __future__ import annotations

import json
import subprocess
import sys

import pytest

from hopscope.harness.proc import (
    DEFAULT_HOME,
    SealedEnvError,
    popen_sealed,
    run_sealed,
    sealed_env,
)

DUMP_ENV = [sys.executable, "-c", "import json, os; print(json.dumps(dict(os.environ)))"]


def test_provenance_sha_filled() -> None:
    from hopscope.harness import proc

    assert "@CYBERAI_SHA@" not in (proc.__doc__ or "")


def test_parent_env_not_inherited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-leak")
    monkeypatch.setenv("HOPSCOPE_BENIGN", "x")
    env = sealed_env()
    assert "OPENAI_API_KEY" not in env and "HOPSCOPE_BENIGN" not in env
    assert env["HOME"] == DEFAULT_HOME and env["PATH"]


def test_path_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PATH", raising=False)
    assert sealed_env()["PATH"] == "/usr/local/bin:/usr/bin:/bin"


def test_allowlist_copies_benign(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSL_CERT_FILE", "/c.pem")
    assert sealed_env(allow=["SSL_CERT_FILE", "ABSENT_VAR"])["SSL_CERT_FILE"] == "/c.pem"


@pytest.mark.parametrize("name", ["github_token", "AWS_SECRET_ACCESS_KEY", "OAUTH_X", "WALLET_SEED"])
def test_credential_shaped_names_refused(name: str) -> None:
    with pytest.raises(SealedEnvError):
        sealed_env(allow=[name])
    with pytest.raises(SealedEnvError):
        sealed_env(extra={name: "v"})


def test_string_argv_refused() -> None:
    with pytest.raises(SealedEnvError):
        run_sealed("echo hi")  # type: ignore[arg-type]
    with pytest.raises(SealedEnvError):
        popen_sealed(b"echo hi")  # type: ignore[arg-type]


def test_child_cannot_see_parent_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOPSCOPE_TEST_TOKEN", "canary")
    out = run_sealed(DUMP_ENV, timeout=30, extra_env={"HOPSCOPE_MODE": "ci"}, check=True)
    child = json.loads(out.stdout)
    assert "HOPSCOPE_TEST_TOKEN" not in child
    assert child["HOPSCOPE_MODE"] == "ci" and child["HOME"] == DEFAULT_HOME


def test_popen_sealed_env() -> None:
    p = popen_sealed(DUMP_ENV, stdout=subprocess.PIPE, extra_env={"HOPSCOPE_MODE": "ci"})
    out, _ = p.communicate(timeout=30)
    assert p.returncode == 0 and json.loads(out)["HOPSCOPE_MODE"] == "ci"
