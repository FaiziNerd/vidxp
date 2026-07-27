from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vidxp.capabilities.actor.config import actor_config
from vidxp.core.contracts import (
    CancellationToken,
    IndexConfig,
    StorageRecord,
    batched,
    stable_source_id,
)
from vidxp.core.indexing_common import ProgressCallback
from vidxp.core.storage import IndexStorage


@dataclass
class ActorIndexState:
    known_encodings: list[Any] = field(default_factory=list)
    known_ids: list[str] = field(default_factory=list)
    histories: dict[str, list[Any]] = field(default_factory=dict)
    cluster_sizes: dict[str, int] = field(default_factory=dict)
    processed_frames: int = 0


def _best_face_match(
    face_recognition,
    known_encodings,
    encoding,
    threshold,
):
    if not known_encodings:
        return None
    distances = face_recognition.face_distance(known_encodings, encoding)
    match = int(distances.argmin())
    return match if distances[match] < threshold else None


def _actor_records(
    detections,
    config: IndexConfig,
) -> list[StorageRecord]:
    records = []
    for detection in detections:
        source_id = stable_source_id(
            config.run_id,
            str(config.video_id),
            "actor",
            detection["detection_id"],
        )
        top, right, bottom, left = detection["bbox"]
        records.append(
            StorageRecord(
                source_id=source_id,
                embedding=[0.0],
                metadata={
                    **config.record_identity("actor", source_id),
                    "detection_id": detection["detection_id"],
                    "cluster_id": detection["cluster_id"],
                    "frame_index": detection["frame_index"],
                    "timestamp": detection["timestamp"],
                    "bbox_top": top,
                    "bbox_right": right,
                    "bbox_bottom": bottom,
                    "bbox_left": left,
                },
            )
        )
    return records


def process_actor_samples(
    samples,
    *,
    state: ActorIndexState,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
) -> None:
    import face_recognition
    import numpy as np

    settings = actor_config(config)
    for group in batched(samples, settings.batch_size):
        cancellation.raise_if_cancelled()
        detections = []
        for sample in group:
            cancellation.raise_if_cancelled()
            locations = face_recognition.face_locations(sample.frame)
            encodings = face_recognition.face_encodings(
                sample.frame,
                locations,
                num_jitters=settings.num_jitters,
            )
            for ordinal, (encoding, location) in enumerate(
                zip(encodings, locations)
            ):
                match = _best_face_match(
                    face_recognition,
                    state.known_encodings,
                    encoding,
                    settings.match_threshold,
                )
                if match is None:
                    cluster_id = str(len(state.known_ids) + 1)
                    state.known_ids.append(cluster_id)
                    state.known_encodings.append(encoding)
                    state.histories[cluster_id] = [encoding]
                else:
                    cluster_id = state.known_ids[match]
                    history = state.histories[cluster_id]
                    history.append(encoding)
                    if len(history) > 5:
                        history.pop(0)
                    state.known_encodings[match] = np.mean(history, axis=0)
                state.cluster_sizes[cluster_id] = (
                    state.cluster_sizes.get(cluster_id, 0) + 1
                )
                detections.append(
                    {
                        "detection_id": (
                            f"d{sample.frame_index:012d}-{ordinal:04d}"
                        ),
                        "cluster_id": cluster_id,
                        "frame_index": sample.frame_index,
                        "timestamp": sample.timestamp,
                        "bbox": tuple(int(value) for value in location),
                    }
                )
            state.processed_frames += 1
        storage.upsert(
            "actor",
            _actor_records(detections, config),
            batch_size=config.storage_batch_size,
            cancellation=cancellation,
        )


def finalize_actor_index(
    state: ActorIndexState,
    *,
    config: IndexConfig,
    storage: IndexStorage,
) -> tuple[int, int]:
    settings = actor_config(config)
    rejected = [
        cluster_id
        for cluster_id, size in state.cluster_sizes.items()
        if size < settings.minimum_detections
    ]
    for cluster_id in rejected:
        storage.delete_records(
            "actor",
            video_id=str(config.video_id),
            filters={"cluster_id": cluster_id},
        )
    retained = {
        cluster_id: size
        for cluster_id, size in state.cluster_sizes.items()
        if size >= settings.minimum_detections
    }
    return sum(retained.values()), len(retained)


class ActorVisualProcessor:
    def batch_size(self, config: IndexConfig) -> int:
        return actor_config(config).batch_size

    def prepare(
        self,
        config: IndexConfig,
        progress: ProgressCallback | None,
    ) -> ActorIndexState:
        return ActorIndexState()

    def process(
        self,
        samples,
        *,
        state: ActorIndexState,
        info,
        config: IndexConfig,
        storage: IndexStorage,
        cancellation: CancellationToken,
    ) -> None:
        process_actor_samples(
            samples,
            state=state,
            config=config,
            storage=storage,
            cancellation=cancellation,
        )

    def finalize(
        self,
        state: ActorIndexState,
        *,
        config: IndexConfig,
        storage: IndexStorage,
    ) -> tuple[dict[str, Any], int]:
        detections, clusters = finalize_actor_index(
            state,
            config=config,
            storage=storage,
        )
        return (
            {
                "actor_frames": state.processed_frames,
                "actor_detections": detections,
                "actor_clusters": clusters,
            },
            state.processed_frames,
        )


VISUAL_PROCESSOR = ActorVisualProcessor()
