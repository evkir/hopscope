from __future__ import annotations

import pytest

from hopscope import __version__
from hopscope.cli import main


def test_version_string() -> None:
    assert __version__ == "0.0.1"


def test_cli_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "hopscope 0.0.1" in capsys.readouterr().out


def test_cli_no_args_returns_zero() -> None:
    assert main([]) == 0


def test_cli_help_has_description(capsys: pytest.CaptureFixture[str]) -> None:
    main([])
    assert "hopscope command-line interface" in capsys.readouterr().out


def test_cli_demo_prints_excess(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "EXCESS: net:post:ops.evil.test, secrets:get:*" in out and "OUT-OF-ROOT" in out
