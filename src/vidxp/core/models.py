from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module


@dataclass(frozen=True)
class RuntimeDependency:
    label: str
    module: str
    distribution: str


INDEXING_DEPENDENCIES = {
    "dialogue": (
        RuntimeDependency("ChromaDB", "chromadb", "chromadb"),
        RuntimeDependency(
            "Sentence Transformers",
            "sentence_transformers",
            "sentence-transformers",
        ),
    ),
    "scene": (
        RuntimeDependency("ChromaDB", "chromadb", "chromadb"),
        RuntimeDependency("CLIP", "clip", "clip-anytorch"),
        RuntimeDependency("NumPy", "numpy", "numpy"),
        RuntimeDependency("OpenCV", "cv2", "opencv-python"),
        RuntimeDependency("Pillow", "PIL.Image", "Pillow"),
        RuntimeDependency("PyTorch", "torch", "torch"),
    ),
    "actor": (
        RuntimeDependency("ChromaDB", "chromadb", "chromadb"),
        RuntimeDependency(
            "face recognition",
            "face_recognition",
            "face-recognition",
        ),
        RuntimeDependency("NumPy", "numpy", "numpy"),
        RuntimeDependency("OpenCV", "cv2", "opencv-python"),
    ),
    "transcription": (
        RuntimeDependency("MoviePy", "moviepy.editor", "moviepy"),
        RuntimeDependency("WhisperX", "whisperx", "whisperx"),
    ),
}

PROVENANCE_ONLY_DISTRIBUTIONS = (
    "dlib",
    "face-recognition-models",
    "filelock",
)


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


def selected_dependencies(
    modalities: tuple[str, ...],
    *,
    needs_transcription: bool,
) -> tuple[RuntimeDependency, ...]:
    dependencies = [
        dependency
        for modality in modalities
        for dependency in INDEXING_DEPENDENCIES[modality]
    ]
    if needs_transcription:
        dependencies.extend(INDEXING_DEPENDENCIES["transcription"])
    return tuple(
        {
            dependency.module: dependency
            for dependency in dependencies
        }.values()
    )


def runtime_distributions() -> tuple[str, ...]:
    distributions = {
        dependency.distribution
        for group in INDEXING_DEPENDENCIES.values()
        for dependency in group
    }
    distributions.update(PROVENANCE_ONLY_DISTRIBUTIONS)
    return tuple(sorted(distributions, key=str.lower))


def clear_model_cache() -> None:
    get_embedder.cache_clear()
    get_clip_model.cache_clear()
    get_whisper_model.cache_clear()
    get_alignment_model.cache_clear()


def dependency_failures(
    modalities: tuple[str, ...],
    *,
    needs_transcription: bool,
) -> list[tuple[str, str]]:
    failures = []
    for dependency in selected_dependencies(
        modalities,
        needs_transcription=needs_transcription,
    ):
        try:
            import_module(dependency.module)
        except Exception as exc:
            failures.append(
                (dependency.label, f"{type(exc).__name__}: {exc}")
            )
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
