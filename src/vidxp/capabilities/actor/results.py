from __future__ import annotations

from pathlib import Path

from vidxp.capabilities.schemas import (
    ActorClusterSummary,
    ActorDetection,
    ActorRenderResult,
)
from vidxp.core.contracts import IndexConfig
from vidxp.core.storage import IndexStorage
from vidxp.core.video import render_actor_video


class ActorClusterNotFoundError(LookupError):
    """Raised when an actor cluster has no retained detections."""


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
        records = active_storage.records(
            "actor",
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
) -> list[ActorDetection]:
    if config.video_id is None:
        raise ValueError("IndexConfig.video_id is required for actor results.")
    owns_storage = storage is None
    active_storage = storage or IndexStorage(config)
    try:
        records = active_storage.records(
            "actor",
            video_id=config.video_id,
            filters={"cluster_id": cluster_id},
        )
    finally:
        if owns_storage:
            active_storage.close()

    detections = [
        ActorDetection(
            **{
                key: value
                for key, value in record.items()
                if not key.startswith("bbox_")
            },
            bbox=(
                int(record["bbox_top"]),
                int(record["bbox_right"]),
                int(record["bbox_bottom"]),
                int(record["bbox_left"]),
            ),
        )
        for record in records
    ]
    return sorted(
        detections,
        key=lambda item: (item.frame_index, item.detection_id),
    )


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
    return ActorRenderResult(
        output_path=destination,
        detection_count=len(detections),
    )
