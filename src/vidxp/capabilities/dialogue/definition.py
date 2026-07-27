from __future__ import annotations

from typing import Any, Mapping

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from vidxp.capabilities.contracts import (
    CapabilityDefinition,
    OperationDefinition,
    PreparationContext,
    RuntimeCheck,
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


FFMPEG = RuntimeCheck(
    label="FFmpeg",
    check=ffmpeg_binary,
    applies_to=lambda source: source.transcript is None,
)


def filter_requirements_for_source(
    source: VideoSource,
    requirements: tuple[Requirement, ...],
) -> tuple[Requirement, ...]:
    if source.transcript is not None:
        needed = {"chromadb", "sentence-transformers"}
        return tuple(
            requirement
            for requirement in requirements
            if canonicalize_name(requirement.name) in needed
        )
    return requirements


def prepare_models(
    context: PreparationContext,
    progress: ProgressCallback | None,
) -> tuple[str, ...]:
    settings = DialogueConfig.model_validate(context.settings)
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
    get_embedder(settings.sentence_model, context.device)
    prepared.append(settings.sentence_model)
    report(
        "transcription_model",
        f"Preparing transcription model: WhisperX {settings.whisper_model}",
    )
    get_whisper_model(settings.whisper_model, context.device)
    prepared.append(settings.whisper_model)
    if settings.alignment_language:
        report(
            "alignment_model",
            f"Preparing the {settings.alignment_language} alignment model.",
        )
        get_alignment_model(settings.alignment_language, context.device)
        prepared.append(
            f"whisperx-alignment:{settings.alignment_language}"
        )
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
    runtime_checks=(FFMPEG,),
    requirement_filter=filter_requirements_for_source,
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
