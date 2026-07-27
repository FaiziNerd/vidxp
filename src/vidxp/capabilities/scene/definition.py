from __future__ import annotations

from typing import Any, Mapping

from vidxp.capabilities.contracts import (
    CapabilityDefinition,
    OperationDefinition,
    PreparationContext,
    RuntimeDependency,
)
from vidxp.capabilities.scene.config import SceneConfig, scene_config
from vidxp.capabilities.scene.indexing import VISUAL_PROCESSOR
from vidxp.capabilities.scene.models import get_clip_model
from vidxp.capabilities.scene.operations import search_operation
from vidxp.capabilities.schemas import SearchInput, SearchResult
from vidxp.capabilities.visual import index_capabilities
from vidxp.core.contracts import IndexConfig, VideoSource
from vidxp.core.indexing_common import ProgressCallback


DEPENDENCIES = (
    RuntimeDependency(
        label="ChromaDB",
        distribution="chromadb",
        module="chromadb",
    ),
    RuntimeDependency(
        label="CLIP",
        distribution="clip-anytorch",
        module="clip",
    ),
    RuntimeDependency(
        label="NumPy",
        distribution="numpy",
        module="numpy",
    ),
    RuntimeDependency(
        label="OpenCV",
        distribution="opencv-python",
        module="cv2",
    ),
    RuntimeDependency(
        label="Pillow",
        distribution="Pillow",
        module="PIL.Image",
    ),
    RuntimeDependency(
        label="PyTorch",
        distribution="torch",
        module="torch",
    ),
)


def prepare_models(
    context: PreparationContext,
    progress: ProgressCallback | None,
) -> tuple[str, ...]:
    settings = SceneConfig.model_validate(context.settings)
    if progress is not None:
        progress(
            {
                "state": "preparing",
                "stage": "scene_model",
                "message": (
                    f"Preparing scene model: CLIP {settings.model}"
                ),
            }
        )
    get_clip_model(settings.model, context.device)
    return (settings.model,)


def model_manifest(
    config: IndexConfig,
    _sources: tuple[VideoSource, ...],
) -> Mapping[str, Any]:
    return {"scene": scene_config(config).model}


DEFINITION = CapabilityDefinition(
    name="scene",
    description="Index and search visual scenes.",
    extra="scene",
    config_model=SceneConfig,
    collection_name="scene",
    indexer=index_capabilities,
    index_processor=VISUAL_PROCESSOR,
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
