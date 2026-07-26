from __future__ import annotations

from functools import lru_cache
from importlib import import_module


INDEXING_DEPENDENCIES = {
    "dialogue": (
        ("ChromaDB", "chromadb"),
        ("Sentence Transformers", "sentence_transformers"),
    ),
    "scene": (
        ("ChromaDB", "chromadb"),
        ("CLIP", "clip"),
        ("NumPy", "numpy"),
        ("OpenCV", "cv2"),
        ("Pillow", "PIL.Image"),
        ("PyTorch", "torch"),
    ),
    "actor": (
        ("ChromaDB", "chromadb"),
        ("face recognition", "face_recognition"),
        ("NumPy", "numpy"),
        ("OpenCV", "cv2"),
    ),
    "transcription": (
        ("MoviePy", "moviepy.editor"),
        ("WhisperX", "whisperx"),
    ),
}


@lru_cache
def get_embedder(model_name: str, device: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device=device)


@lru_cache
def get_clip_model(model_name: str, device: str):
    import clip

    return clip.load(model_name, device=device)


@lru_cache
def get_whisper_model(model_name: str, device: str):
    import whisperx

    return whisperx.load_model(model_name, device, compute_type="float32")


@lru_cache
def get_alignment_model(language: str, device: str):
    import whisperx

    return whisperx.load_align_model(language_code=language, device=device)


def dependency_failures(
    modalities: tuple[str, ...],
    *,
    needs_transcription: bool,
) -> list[tuple[str, str]]:
    dependencies: list[tuple[str, str]] = []
    for modality in modalities:
        dependencies.extend(INDEXING_DEPENDENCIES[modality])
    if needs_transcription:
        dependencies.extend(INDEXING_DEPENDENCIES["transcription"])

    failures = []
    for label, module_name in dict.fromkeys(dependencies):
        try:
            import_module(module_name)
        except Exception as exc:
            failures.append((label, f"{type(exc).__name__}: {exc}"))
    return failures


def require_dependencies(
    modalities: tuple[str, ...],
    *,
    needs_transcription: bool,
) -> None:
    failures = dependency_failures(
        modalities,
        needs_transcription=needs_transcription,
    )
    if failures:
        details = "; ".join(f"{label}: {error}" for label, error in failures)
        raise RuntimeError(f"Indexing dependencies are unavailable: {details}")
