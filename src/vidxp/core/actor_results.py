from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vidxp.core.contracts import IndexConfig
from vidxp.core.storage import IndexStorage
from vidxp.core.video import render_actor_video


class ActorClusterNotFoundError(LookupError):
    """Raised when an actor cluster has no retained detections."""


@dataclass(frozen=True)
class ActorRenderResult:
    output_path: Path
    detection_count: int


@dataclass(frozen=True)
class ActorClusterSummary:
    cluster_id: str
    video_id: str
    detection_count: int
    first_timestamp: float
    last_timestamp: float

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "video_id": self.video_id,
            "detection_count": self.detection_count,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
        }


def actor_clusters(
    config: IndexConfig,
    *,
    storage: IndexStorage | None = None,
) -> tuple[ActorClusterSummary, ...]:
    if config.video_id is None:
        raise ValueError("IndexConfig.video_id is required for actor results.")
    owns_storage = storage is None
    active_storage = storage or IndexStorage(config)
    try:
        records = active_storage.actor_cluster_records(
            video_id=config.video_id,
        )
    finally:
        if owns_storage:
            active_storage.close()

    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(str(record["cluster_id"]), []).append(record)
    return tuple(
        ActorClusterSummary(
            cluster_id=cluster_id,
            video_id=config.video_id,
            detection_count=len(cluster_records),
            first_timestamp=min(
                float(record["timestamp"]) for record in cluster_records
            ),
            last_timestamp=max(
                float(record["timestamp"]) for record in cluster_records
            ),
        )
        for cluster_id, cluster_records in sorted(grouped.items())
    )


def actor_detections(
    config: IndexConfig,
    cluster_id: str,
    *,
    storage: IndexStorage | None = None,
) -> list[dict]:
    if config.video_id is None:
        raise ValueError("IndexConfig.video_id is required for actor results.")
    owns_storage = storage is None
    active_storage = storage or IndexStorage(config)
    try:
        records = active_storage.actor_detections(
            video_id=config.video_id,
            cluster_id=cluster_id,
        )
    finally:
        if owns_storage:
            active_storage.close()

    return [
        {
            **record,
            "bbox": (
                int(record["bbox_top"]),
                int(record["bbox_right"]),
                int(record["bbox_bottom"]),
                int(record["bbox_left"]),
            ),
        }
        for record in records
    ]


def render_actor_result(
    config: IndexConfig,
    cluster_id: str,
    input_path: str | Path,
    output_path: str | Path,
    *,
    storage: IndexStorage | None = None,
) -> ActorRenderResult:
    detections = actor_detections(config, cluster_id, storage=storage)
    if not detections:
        raise ActorClusterNotFoundError(
            f"Actor cluster {cluster_id} was not found in the completed index."
        )
    destination = Path(output_path)
    render_actor_video(input_path, destination, cluster_id, detections)
    return ActorRenderResult(destination, len(detections))
