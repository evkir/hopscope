from __future__ import annotations

from pathlib import Path

import pytest

from hopscope.harness.gpu_guard import LOCK_ENV, GPUBusy, check_gpu_free, lock_path
from hopscope.harness.llm_client import make_backend


class Fake:
    def __init__(self, loaded: list[str]) -> None:
        self.loaded = loaded

    def loaded_models(self) -> list[str]:
        return list(self.loaded)


def test_lock_file_refuses(tmp_path: Path) -> None:
    lock = tmp_path / "ppd.lock"
    lock.touch()
    with pytest.raises(GPUBusy, match="PPD collection"):
        check_gpu_free(Fake([]), lock=lock)


def test_loaded_model_refuses(tmp_path: Path) -> None:
    with pytest.raises(GPUBusy, match="already holds qwen3:14b"):
        check_gpu_free(Fake(["qwen3:14b"]), lock=tmp_path / "absent")


def test_free_gpu_passes(tmp_path: Path) -> None:
    check_gpu_free(Fake([]), lock=tmp_path / "absent")


def test_lock_path_env_and_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(LOCK_ENV, str(tmp_path / "x.lock"))
    assert lock_path() == tmp_path / "x.lock"
    monkeypatch.delenv(LOCK_ENV)
    assert lock_path() == Path.home() / ".ppd-collection.lock"


def test_make_backend_live_is_guarded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lock = tmp_path / "ppd.lock"
    lock.touch()
    monkeypatch.setenv(LOCK_ENV, str(lock))
    with pytest.raises(GPUBusy):
        make_backend("live")


def test_check_lock_alone(tmp_path: Path) -> None:
    from hopscope.harness.gpu_guard import check_lock

    check_lock(tmp_path / "absent")
    lock = tmp_path / "ppd.lock"
    lock.touch()
    with pytest.raises(GPUBusy):
        check_lock(lock)
