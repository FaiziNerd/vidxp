from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from vidxp.capabilities.contracts import CapabilityInput, CapabilityOutput
from vidxp.core.contracts import INDEX_SCHEMA_VERSION


class SearchInput(CapabilityInput):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, gt=0)


class SearchHit(CapabilityOutput):
    rank: int = Field(gt=0)
    video_id: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    score: float
    raw_distance: float
    modality: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SearchResult(CapabilityOutput):
    query_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    modality: str = Field(min_length=1)
    hits: tuple[SearchHit, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": INDEX_SCHEMA_VERSION,
            **self.model_dump(mode="json"),
        }

    def to_prediction(self) -> dict[str, list[dict[str, Any]]]:
        return {
            self.query_id: [
                hit.model_dump(mode="json") for hit in self.hits
            ]
        }


class ActorClustersInput(CapabilityInput):
    pass


class ActorClusterSummary(CapabilityOutput):
    cluster_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    detection_count: int = Field(ge=0)
    first_timestamp: float = Field(ge=0)
    last_timestamp: float = Field(ge=0)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ActorClustersOutput(CapabilityOutput):
    clusters: tuple[ActorClusterSummary, ...] = ()


class ActorDetectionsInput(CapabilityInput):
    cluster_id: str = Field(min_length=1)


class ActorDetection(CapabilityOutput):
    detection_id: str = Field(min_length=1)
    cluster_id: str = Field(min_length=1)
    frame_index: int = Field(ge=0)
    timestamp: float = Field(ge=0)
    bbox: tuple[int, int, int, int]
    dataset: str
    split: str
    run_id: str
    video_id: str
    modality: str
    source_id: str


class ActorDetectionsOutput(CapabilityOutput):
    cluster_id: str = Field(min_length=1)
    detections: tuple[ActorDetection, ...] = ()


class ActorRenderInput(CapabilityInput):
    cluster_id: str = Field(min_length=1)
    input_path: Path
    output_path: Path


class ActorRenderResult(CapabilityOutput):
    output_path: Path
    detection_count: int = Field(gt=0)
