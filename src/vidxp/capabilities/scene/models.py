from __future__ import annotations

from functools import lru_cache


@lru_cache
def get_clip_model(model_name: str, device: str):
    import clip

    return clip.load(model_name, device=device)


def clear_model_cache() -> None:
    get_clip_model.cache_clear()
