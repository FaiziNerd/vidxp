from __future__ import annotations

from functools import lru_cache


@lru_cache
def get_embedder(model_name: str, device: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device=device)


@lru_cache
def get_whisper_model(model_name: str, device: str):
    import whisperx

    return whisperx.load_model(model_name, device, compute_type="float32")


@lru_cache
def get_alignment_model(language: str, device: str):
    import whisperx

    return whisperx.load_align_model(language_code=language, device=device)


def clear_model_cache() -> None:
    get_embedder.cache_clear()
    get_whisper_model.cache_clear()
    get_alignment_model.cache_clear()
