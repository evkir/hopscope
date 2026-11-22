"""Refuse live mode while the GPU belongs to something else, PPD collection above all.

PPD v0.5 §5 unloads every model before each agent and assumes nothing else loads
one in between. A hopscope live run on the same Ollama server during collection
would break that rule and the reproducibility it protects. Create the lock file
(default ~/.ppd-collection.lock, override with HOPSCOPE_GPU_LOCK) while PPD runs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

LOCK_ENV = "HOPSCOPE_GPU_LOCK"
DEFAULT_LOCK = "~/.ppd-collection.lock"


class GPUBusy(RuntimeError):
    """Live mode refused: the GPU is in use or reserved."""


class HasLoadedModels(Protocol):
    def loaded_models(self) -> list[str]: ...


def lock_path() -> Path:
    return Path(os.environ.get(LOCK_ENV, DEFAULT_LOCK)).expanduser()


def check_gpu_free(backend: HasLoadedModels, lock: Path | None = None) -> None:
    path = lock if lock is not None else lock_path()
    if path.exists():
        raise GPUBusy(f"{path} exists (PPD collection in progress); live mode refused")
    loaded = backend.loaded_models()
    if loaded:
        raise GPUBusy(f"Ollama already holds {', '.join(loaded)}; live mode will not share the GPU")
