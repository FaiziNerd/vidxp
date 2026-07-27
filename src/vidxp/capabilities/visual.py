from __future__ import annotations

from time import perf_counter
from typing import Any, Sequence

from vidxp.capabilities.contracts import CapabilityIndexResult
from vidxp.core.contracts import (
    CancellationToken,
    IndexConfig,
    VideoSource,
)
from vidxp.capabilities.actor.indexing import (
    ActorIndexState,
    finalize_actor_index,
    process_actor_samples,
)
from vidxp.core.indexing_common import ProgressCallback, report_progress
from vidxp.capabilities.scene.indexing import (
    SceneIndexState,
    process_scene_samples,
)
from vidxp.capabilities.scene.models import get_clip_model
from vidxp.core.storage import IndexStorage
from vidxp.core.video import (
    FrameSample,
    FrameStreamStats,
    iter_frame_batches,
    probe_video,
)


def _rgb_samples(samples) -> list[FrameSample]:
    import cv2

    return [
        FrameSample(
            frame_index=sample.frame_index,
            timestamp=sample.timestamp,
            frame=cv2.cvtColor(sample.frame, cv2.COLOR_BGR2RGB),
        )
        for sample in samples
    ]


def _consume_visual_stream(
    source: VideoSource,
    *,
    selected: tuple[str, ...],
    expected: int,
    info,
    scene_state: SceneIndexState | None,
    actor_state: ActorIndexState | None,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
    progress: ProgressCallback | None,
    timings: dict[str, float],
) -> FrameStreamStats:
    stream_stats = FrameStreamStats()
    decode_batch_size = max(
        config.scene_batch_size if "scene" in selected else 0,
        config.actor_batch_size if "actor" in selected else 0,
    )
    stream = iter(
        iter_frame_batches(
            source.path,
            frame_stride=config.frame_stride,
            batch_size=decode_batch_size,
            cancellation=cancellation,
            stats=stream_stats,
        )
    )
    while True:
        stream_started = perf_counter()
        try:
            samples = next(stream)
        except StopIteration:
            timings["frame_stream"] += perf_counter() - stream_started
            break
        rgb_samples = _rgb_samples(samples)
        timings["frame_stream"] += perf_counter() - stream_started

        if scene_state is not None:
            scene_started = perf_counter()
            process_scene_samples(
                rgb_samples,
                state=scene_state,
                info=info,
                config=config,
                storage=storage,
                cancellation=cancellation,
            )
            timings["scene"] += perf_counter() - scene_started

        if actor_state is not None:
            actor_started = perf_counter()
            process_actor_samples(
                rgb_samples,
                state=actor_state,
                config=config,
                storage=storage,
                cancellation=cancellation,
            )
            timings["actor"] += perf_counter() - actor_started

        report_progress(
            progress,
            "visual_indexing",
            "Indexing the shared sampled-frame stream.",
            stream_stats.frames_materialized,
            expected,
        )
    return stream_stats


def _visual_summary(
    *,
    scene_state: SceneIndexState | None,
    actor_state: ActorIndexState | None,
    stream_stats: FrameStreamStats,
    actor_detections: int,
    actor_clusters: int,
    info,
) -> dict[str, Any]:
    scene_frames = scene_state.stored_frames if scene_state is not None else 0
    actor_frames = (
        actor_state.processed_frames if actor_state is not None else 0
    )
    sampled_frames = (
        stream_stats.frames_materialized
        or max(scene_frames, actor_frames)
    )
    return {
        "source_frames_advanced": stream_stats.frames_advanced,
        "sampled_frames": sampled_frames,
        "processed_frames": sampled_frames,
        "frame_operations": scene_frames + actor_frames,
        "scene_frames": scene_frames,
        "actor_frames": actor_frames,
        "actor_detections": actor_detections,
        "actor_clusters": actor_clusters,
        "duration": info.duration,
        "fps": info.fps,
    }


def index_visuals(
    source: VideoSource,
    *,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
    progress: ProgressCallback | None = None,
    modalities: Sequence[str] | None = None,
) -> CapabilityIndexResult:
    if config.video_id is None:
        raise ValueError("IndexConfig.video_id is required for indexing.")
    if source.path is None:
        raise ValueError("Scene and actor indexing require a video path.")

    selected = tuple(
        modality
        for modality in (
            config.enabled_modalities if modalities is None else modalities
        )
        if modality in {"scene", "actor"}
    )
    if not selected:
        raise ValueError("At least one visual modality must be selected.")

    started = perf_counter()
    info = probe_video(source.path)
    expected = (info.frame_count + config.frame_stride - 1) // config.frame_stride
    scene_state = None
    actor_state = ActorIndexState() if "actor" in selected else None
    timings = {"frame_stream": 0.0, "scene": 0.0, "actor": 0.0}

    if "scene" in selected:
        scene_started = perf_counter()
        report_progress(
            progress,
            "preparing_scene_model",
            f"Preparing scene model: CLIP {config.clip_model}.",
        )
        scene_model, scene_preprocess = get_clip_model(
            config.clip_model,
            config.device,
        )
        scene_state = SceneIndexState(scene_model, scene_preprocess)
        timings["scene"] += perf_counter() - scene_started

    report_progress(
        progress,
        "visual_indexing",
        "Decoding sampled frames for "
        + " and ".join(selected)
        + " indexing.",
        0,
        expected,
    )
    stream_stats = _consume_visual_stream(
        source,
        selected=selected,
        expected=expected,
        info=info,
        scene_state=scene_state,
        actor_state=actor_state,
        config=config,
        storage=storage,
        cancellation=cancellation,
        progress=progress,
        timings=timings,
    )

    actor_detections = actor_clusters = 0
    if actor_state is not None:
        actor_started = perf_counter()
        actor_detections, actor_clusters = finalize_actor_index(
            actor_state,
            config=config,
            storage=storage,
        )
        timings["actor"] += perf_counter() - actor_started
    timings["visual_total"] = perf_counter() - started

    return CapabilityIndexResult(
        summary=_visual_summary(
            scene_state=scene_state,
            actor_state=actor_state,
            stream_stats=stream_stats,
            actor_detections=actor_detections,
            actor_clusters=actor_clusters,
            info=info,
        ),
        timings=timings,
    )


def index_capabilities(
    source: VideoSource,
    *,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
    progress: ProgressCallback | None = None,
    modalities: Sequence[str] | None = None,
) -> CapabilityIndexResult:
    """Registry-facing wrapper that keeps the shared indexer patchable."""

    return index_visuals(
        source,
        config=config,
        storage=storage,
        cancellation=cancellation,
        progress=progress,
        modalities=modalities,
    )
