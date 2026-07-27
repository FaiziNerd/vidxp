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
