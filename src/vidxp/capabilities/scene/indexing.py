from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vidxp.capabilities.scene.config import scene_config
from vidxp.core.contracts import (
    CancellationToken,
    IndexConfig,
    StorageRecord,
    batched,
    stable_source_id,
)
from vidxp.core.storage import IndexStorage


@dataclass
class SceneIndexState:
    model: Any
    preprocess: Any
    stored_frames: int = 0


def encode_scene_batch(samples, model, preprocess, device):
    import torch
    from PIL import Image

    images = torch.stack(
        [preprocess(Image.fromarray(sample.frame)) for sample in samples]
    ).to(device)
    with torch.no_grad():
        features = model.encode_image(images)
        features /= features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy().tolist()


def scene_records(
    samples,
    vectors,
    info,
    config: IndexConfig,
) -> list[StorageRecord]:
    records = []
    for sample, vector in zip(samples, vectors):
        end = min(
            info.duration,
            sample.timestamp + config.frame_stride / info.fps,
        )
        if end <= sample.timestamp:
            end = sample.timestamp + 1 / info.fps
        source_id = stable_source_id(
            config.run_id,
            str(config.video_id),
            "scene",
            f"f{sample.frame_index:012d}",
        )
        records.append(
            StorageRecord(
                source_id=source_id,
                embedding=vector,
                metadata={
                    **config.record_identity("scene", source_id),
                    "frame_index": sample.frame_index,
                    "timestamp": sample.timestamp,
                    "start": sample.timestamp,
                    "end": end,
                    "fps": info.fps,
                    "duration": info.duration,
                },
            )
        )
    return records


def process_scene_samples(
    samples,
    *,
    state: SceneIndexState,
    info,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
) -> None:
    settings = scene_config(config)
    for group in batched(samples, settings.batch_size):
        cancellation.raise_if_cancelled()
        vectors = encode_scene_batch(
            group,
            state.model,
            state.preprocess,
            config.device,
        )
        state.stored_frames += storage.upsert(
            "scene",
            scene_records(group, vectors, info, config),
            batch_size=config.storage_batch_size,
            cancellation=cancellation,
        )
