from __future__ import annotations

from typing import Any, Mapping

from vidxp.capabilities.contracts import (
    CapabilityDefinition,
    OperationDefinition,
    RuntimeDependency,
)
from vidxp.capabilities.dialogue.config import DialogueConfig, dialogue_config
from vidxp.capabilities.dialogue.models import (
    get_alignment_model,
    get_embedder,
    get_whisper_model,
)
from vidxp.capabilities.dialogue.operations import (
    index_capability,
    search_operation,
)
from vidxp.capabilities.schemas import SearchInput, SearchResult
from vidxp.core.contracts import IndexConfig, VideoSource
from vidxp.core.indexing_common import ProgressCallback
from vidxp.core.video import ffmpeg_binary


CHROMA = RuntimeDependency("ChromaDB", "chromadb", "chromadb")
SENTENCE_TRANSFORMERS = RuntimeDependency(
    "Sentence Transformers",
    "sentence-transformers",
    "sentence_transformers",
)
MOVIEPY = RuntimeDependency("MoviePy", "moviepy", "moviepy.editor")
WHISPERX = RuntimeDependency("WhisperX", "whisperx", "whisperx")
FFMPEG = RuntimeDependency("FFmpeg", check=ffmpeg_binary)

DEPENDENCIES = (
    CHROMA,
    SENTENCE_TRANSFORMERS,
    MOVIEPY,
    WHISPERX,
    FFMPEG,
)


def dependencies_for_source(
    source: VideoSource,
) -> tuple[RuntimeDependency, ...]:
    if source.transcript is not None:
        return CHROMA, SENTENCE_TRANSFORMERS
    return DEPENDENCIES


def prepare_models(
    config: IndexConfig,
    language: str | None,
    progress: ProgressCallback | None,
) -> tuple[str, ...]:
    settings = dialogue_config(config)
    prepared = []

    def report(stage: str, message: str) -> None:
        if progress is not None:
            progress(
                {
                    "state": "preparing",
                    "stage": stage,
                    "message": message,
                }
            )

    report(
        "dialogue_model",
        f"Preparing dialogue model: {settings.sentence_model}",
    )
    get_embedder(settings.sentence_model, config.device)
    prepared.append(settings.sentence_model)
    report(
        "transcription_model",
        f"Preparing transcription model: WhisperX {settings.whisper_model}",
    )
    get_whisper_model(settings.whisper_model, config.device)
    prepared.append(settings.whisper_model)
    if language:
        report(
            "alignment_model",
            f"Preparing the {language} alignment model.",
        )
        get_alignment_model(language, config.device)
        prepared.append(f"whisperx-alignment:{language}")
    return tuple(prepared)


def model_manifest(
    config: IndexConfig,
    sources: tuple[VideoSource, ...],
) -> Mapping[str, Any]:
    settings = dialogue_config(config)
    result: dict[str, Any] = {"dialogue": settings.sentence_model}
    if any(source.transcript is None for source in sources):
        result["transcription"] = settings.whisper_model
    return result


DEFINITION = CapabilityDefinition(
    name="dialogue",
    description="Index and search spoken dialogue.",
    extra="dialogue",
    config_model=DialogueConfig,
    collection_name="dialogue",
    indexer=index_capability,
    index_stage="dialogue_indexing",
    dependencies=DEPENDENCIES,
    dependencies_for_source=dependencies_for_source,
    prepare=prepare_models,
    model_manifest=model_manifest,
    operations={
        "search": OperationDefinition(
            input_model=SearchInput,
            output_model=SearchResult,
            handler=search_operation,
        )
    },
)
