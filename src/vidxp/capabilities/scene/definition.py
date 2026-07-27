from __future__ import annotations

from typing import Any, Mapping

from vidxp.capabilities.contracts import (
    CapabilityDefinition,
    OperationDefinition,
    RuntimeDependency,
)
from vidxp.capabilities.scene.models import get_clip_model
from vidxp.capabilities.scene.operations import search_operation
from vidxp.capabilities.schemas import SearchInput, SearchResult
from vidxp.capabilities.visual import index_capabilities
from vidxp.core.contracts import IndexConfig, VideoSource
from vidxp.core.indexing_common import ProgressCallback


DEPENDENCIES = (
    RuntimeDependency("ChromaDB", "chromadb", "chromadb"),
    RuntimeDependency("CLIP", "clip-anytorch", "clip"),
    RuntimeDependency("NumPy", "numpy", "numpy"),
    RuntimeDependency("OpenCV", "opencv-python", "cv2"),
    RuntimeDependency("Pillow", "Pillow", "PIL.Image"),
    RuntimeDependency("PyTorch", "torch", "torch"),
)


def prepare_models(
    config: IndexConfig,
    _language: str | None,
    progress: ProgressCallback | None,
) -> tuple[str, ...]:
    if progress is not None:
        progress(
            {
                "state": "preparing",
                "stage": "scene_model",
                "message": (
                    f"Preparing scene model: CLIP {config.clip_model}"
                ),
            }
        )
    get_clip_model(config.clip_model, config.device)
    return (config.clip_model,)


def model_manifest(
    config: IndexConfig,
    _sources: tuple[VideoSource, ...],
) -> Mapping[str, Any]:
    return {"scene": config.clip_model}


DEFINITION = CapabilityDefinition(
    name="scene",
    description="Index and search visual scenes.",
    extra="scene",
    collection_name="scene",
    indexer=index_capabilities,
    index_stage="visual_indexing",
    dependencies=DEPENDENCIES,
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
