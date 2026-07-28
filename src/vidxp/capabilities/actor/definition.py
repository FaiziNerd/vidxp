from __future__ import annotations

from typing import Any, Mapping

from vidxp.capabilities.actor.config import ActorConfig, actor_config
from vidxp.capabilities.actor.indexing import VISUAL_PROCESSOR
from vidxp.capabilities.actor.operations import (
    clusters_operation,
    detections_operation,
    render_operation,
)
from vidxp.capabilities.contracts import (
    CapabilityDefinition,
    OperationDefinition,
)
from vidxp.capabilities.actor.schemas import (
    ActorClustersInput,
    ActorClustersOutput,
    ActorDetectionsInput,
    ActorDetectionsOutput,
    ActorRenderInput,
    ActorRenderResult,
)
from vidxp.capabilities.visual import index_capabilities
from vidxp.core.contracts import IndexConfig, VideoSource

def model_manifest(
    config: IndexConfig,
    _sources: tuple[VideoSource, ...],
) -> Mapping[str, Any]:
    settings = actor_config(config)
    return {
        "actor": {
            "library": "face_recognition",
            "match_threshold": settings.match_threshold,
            "num_jitters": settings.num_jitters,
            "minimum_detections": settings.minimum_detections,
        }
    }


def cli_app():
    from vidxp.capabilities.actor.cli import app

    return app


DEFINITION = CapabilityDefinition(
    name="actor",
    description="Index, inspect, and render actor clusters.",
    extra="actor",
    config_model=ActorConfig,
    collection_name="actor",
    indexer=index_capabilities,
    index_processor=VISUAL_PROCESSOR,
    index_stage="visual_indexing",
    model_manifest=model_manifest,
    operations={
        "clusters": OperationDefinition(
            input_model=ActorClustersInput,
            output_model=ActorClustersOutput,
            handler=clusters_operation,
        ),
        "detections": OperationDefinition(
            input_model=ActorDetectionsInput,
            output_model=ActorDetectionsOutput,
            handler=detections_operation,
        ),
        "render": OperationDefinition(
            input_model=ActorRenderInput,
            output_model=ActorRenderResult,
            handler=render_operation,
        ),
    },
    cli_name="actors",
    cli_factory=cli_app,
)
