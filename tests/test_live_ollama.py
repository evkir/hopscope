from __future__ import annotations

import pytest

from hopscope.harness.gpu_guard import check_gpu_free
from hopscope.harness.llm_client import LIVE_MODELS, OllamaBackend, OllamaConfig

PROMPT = [{"role": "user", "content": "Name one prime number between 10 and 20. One word."}]


@pytest.mark.live
@pytest.mark.parametrize(("model", "think"), LIVE_MODELS)
def test_same_seed_same_reply_after_fresh_load(model: str, think: bool | None) -> None:
    """PPD v0.5 §5: under one seed, an agent started on a freshly loaded model repeats itself."""
    b = OllamaBackend(OllamaConfig(model=model, think=think, seed=12345, num_predict=256))
    check_gpu_free(b)
    try:
        b.unload()
        first = b.chat(PROMPT, agent="probe")
        b.unload()
        second = b.chat(PROMPT, agent="probe")
    finally:
        b.unload()
    assert first == second
