from __future__ import annotations

from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Callable, Sequence

from filelock import FileLock, Timeout

from vidxp.core.contracts import (
    INDEX_SCHEMA_VERSION,
    CancellationToken,
    IndexCancelledError,
    IndexConfig,
    IndexSchemaError,
    VideoSource,
)
from vidxp.core.indexing_dialogue import index_dialogue
from vidxp.core.indexing_visual import index_visuals
from vidxp.core.manifest import (
    ManifestStore,
    combined_checksum,
    source_checksum,
    source_checksums,
)
from vidxp.core.models import require_dependencies
from vidxp.core.storage import IndexStorage
from vidxp.index_state import (
    IndexingInProgressError,
    write_index_status,
)


ProgressCallback = Callable[[dict[str, Any]], None]
_INDEXING_LOCK = Lock()


class _RunLock:
    def __init__(self, run_directory: Path):
        self.path = run_directory / ".indexing.lock"
        self.lock = FileLock(self.path)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.lock.acquire(timeout=0)
        except Timeout as exc:
            raise IndexingInProgressError(
                f"Indexing is already active for {self.path.parent}."
            ) from exc
        return self

    def __exit__(self, *_):
        self.lock.release()


def indexing_in_progress() -> bool:
    return _INDEXING_LOCK.locked()


def local_config_from_status(status: dict[str, Any]) -> IndexConfig:
    summary = status.get("summary") or {}
    if summary.get("index_schema_version") != INDEX_SCHEMA_VERSION:
        raise IndexSchemaError(
            "The saved index predates the benchmark-ready schema. "
            "Re-index the video before searching."
        )
    stored = dict(summary.get("configuration") or {})
    stored = {
        key: value
        for key, value in stored.items()
        if key in IndexConfig.__dataclass_fields__
    }
    stored.update(
        {
            "dataset": str(summary["dataset"]),
            "split": str(summary["split"]),
            "run_id": str(summary["run_id"]),
            "video_id": str(summary["video_id"]),
            "storage_directory": "chroma_data",
        }
    )
    if "enabled_modalities" in stored:
        stored["enabled_modalities"] = tuple(stored["enabled_modalities"])
    if "collection_names" in stored:
        stored["collection_names"] = tuple(stored["collection_names"])
    return IndexConfig(**stored)


def _resolve_sources(
    sources: Sequence[VideoSource],
    config: IndexConfig,
) -> list[tuple[str, VideoSource, str, dict[str, str]]]:
    resolved = []
    used_ids = set()
    for source in sources:
        checksums = source_checksums(source)
        checksum = combined_checksum(checksums)
        video_id = source.video_id or config.video_id or checksum
        if video_id in used_ids:
            raise ValueError(f"Duplicate video_id in run: {video_id}")
        used_ids.add(video_id)
        resolved.append((video_id, source, checksum, checksums))
    return sorted(resolved, key=lambda item: item[0])


def _report(
    callback: ProgressCallback | None,
    event: dict[str, Any],
) -> None:
    if callback is not None:
        callback(event)


def _run_modality(
    modality: str,
    source: VideoSource,
    config: IndexConfig,
    storage: IndexStorage,
    manifest: ManifestStore,
    cancellation: CancellationToken,
    progress_callback: ProgressCallback | None,
) -> dict[str, Any]:
    started = perf_counter()
    active_substage: str | None = None
    substage_started = started

    def stage_progress(event: dict[str, Any]) -> None:
        nonlocal active_substage, substage_started
        event_stage = str(event["stage"])
        if active_substage is None:
            active_substage = event_stage
            substage_started = perf_counter()
        elif event_stage != active_substage:
            manifest.record_stage(
                str(config.video_id),
                active_substage,
                perf_counter() - substage_started,
                {},
            )
            active_substage = event_stage
            substage_started = perf_counter()
        _report(
            progress_callback,
            {**event, "video_id": config.video_id},
        )

    try:
        if modality != "dialogue":
            raise ValueError(f"Unsupported non-visual modality: {modality}")
        stats = index_dialogue(
            source,
            config=config,
            storage=storage,
            cancellation=cancellation,
            progress=stage_progress,
        )
    except BaseException:
        if active_substage is not None:
            manifest.record_stage(
                str(config.video_id),
                active_substage,
                perf_counter() - substage_started,
                {"state": "incomplete"},
            )
        raise
    if active_substage is not None:
        manifest.record_stage(
            str(config.video_id),
            active_substage,
            perf_counter() - substage_started,
            {},
        )
    manifest.record_stage(
        str(config.video_id),
        modality,
        perf_counter() - started,
        stats,
    )
    return stats


def _run_visual_modalities(
    modalities: tuple[str, ...],
    source: VideoSource,
    config: IndexConfig,
    storage: IndexStorage,
    manifest: ManifestStore,
    cancellation: CancellationToken,
    progress_callback: ProgressCallback | None,
) -> dict[str, Any]:
    started = perf_counter()

    def report(event: dict[str, Any]) -> None:
        _report(
            progress_callback,
            {**event, "video_id": config.video_id},
        )

    try:
        result = index_visuals(
            source,
            config=config,
            storage=storage,
            cancellation=cancellation,
            progress=report,
            modalities=modalities,
        )
    except BaseException:
        manifest.record_stage(
            str(config.video_id),
            "visual_indexing",
            perf_counter() - started,
            {"state": "incomplete", "modalities": list(modalities)},
        )
        raise

    stats = dict(result.summary)
    timings = dict(result.timings)
    for stage_name in ("frame_stream", "scene", "actor"):
        if stage_name in timings and (
            stage_name == "frame_stream" or stage_name in modalities
        ):
            manifest.record_stage(
                str(config.video_id),
                stage_name,
                float(timings[stage_name]),
                {},
            )
    manifest.record_stage(
        str(config.video_id),
        "visual_indexing",
        float(timings.get("visual_total", perf_counter() - started)),
        stats,
    )
    return stats


def _run_enabled_modalities(
    source: VideoSource,
    config: IndexConfig,
    storage: IndexStorage,
    manifest: ManifestStore,
    cancellation: CancellationToken,
    progress_callback: ProgressCallback | None,
    set_stage: Callable[[str], None],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    visual_modalities = tuple(
        modality
        for modality in config.enabled_modalities
        if modality in {"scene", "actor"}
    )
    visual_complete = False
    for modality in config.enabled_modalities:
        cancellation.raise_if_cancelled()
        if modality in visual_modalities:
            if visual_complete:
                continue
            set_stage("visual_indexing")
            summary.update(
                _run_visual_modalities(
                    visual_modalities,
                    source,
                    config,
                    storage,
                    manifest,
                    cancellation,
                    progress_callback,
                )
            )
            visual_complete = True
            continue

        set_stage(f"{modality}_indexing")
        summary.update(
            _run_modality(
                modality,
                source,
                config,
                storage,
                manifest,
                cancellation,
                progress_callback,
            )
        )
    return summary


def _normalize_frame_summary(summary: dict[str, Any]) -> None:
    scene_frames = int(summary.get("scene_frames", 0))
    actor_frames = int(summary.get("actor_frames", 0))
    summary.setdefault("sampled_frames", max(scene_frames, actor_frames))
    summary.setdefault("processed_frames", int(summary["sampled_frames"]))
    summary.setdefault("frame_operations", scene_frames + actor_frames)
    summary.setdefault(
        "source_frames_advanced",
        int(summary.get("decoded_frames", 0))
        + int(summary.get("actor_decoded_frames", 0)),
    )


def _process_video(
    video_id: str,
    source: VideoSource,
    checksum: str,
    config: IndexConfig,
    storage: IndexStorage,
    manifest: ManifestStore,
    cancellation: CancellationToken,
    progress_callback: ProgressCallback | None,
    *,
    fail_fast: bool,
) -> None:
    video_config = config.for_video(video_id)
    manifest.start_video(video_id)
    summary: dict[str, Any] = {
        "video_id": video_id,
        "modalities": list(config.enabled_modalities),
    }
    stage = "preparing_dependencies"

    def set_stage(value: str) -> None:
        nonlocal stage
        stage = value

    try:
        cancellation.raise_if_cancelled()
        require_dependencies(
            config.enabled_modalities,
            needs_transcription=(
                "dialogue" in config.enabled_modalities
                and source.transcript is None
            ),
        )
        stage = "preparing_storage"
        for modality in config.enabled_modalities:
            storage.delete_video(modality, video_id)

        summary.update(
            _run_enabled_modalities(
                source,
                video_config,
                storage,
                manifest,
                cancellation,
                progress_callback,
                set_stage,
            )
        )
        _normalize_frame_summary(summary)
        manifest.complete_video(
            video_id,
            checksum=checksum,
            summary=summary,
        )
        _report(
            progress_callback,
            {
                "state": "video_complete",
                "stage": "complete",
                "message": f"Completed video {video_id}.",
                "video_id": video_id,
                "summary": summary,
            },
        )
    except (IndexCancelledError, KeyboardInterrupt):
        manifest.interrupt_video(video_id, stage)
        raise
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        manifest.fail_video(video_id, stage, error)
        _report(
            progress_callback,
            {
                "state": "failed",
                "stage": stage,
                "message": f"Indexing failed for video {video_id}.",
                "video_id": video_id,
                "error": error,
            },
        )
        if fail_fast:
            raise


def _run_index_unlocked(
    sources: Sequence[VideoSource],
    config: IndexConfig,
    *,
    progress_callback: ProgressCallback | None = None,
    cancellation: CancellationToken | None = None,
    resume: bool = True,
    reset: bool = False,
    fail_fast: bool = True,
    storage: IndexStorage | None = None,
    manifest_store: ManifestStore | None = None,
) -> dict[str, Any]:
    if not sources:
        raise ValueError("At least one video or transcript source is required.")
    cancellation = cancellation or CancellationToken()
    resolved = _resolve_sources(sources, config)
    owns_storage = storage is None
    store = storage or IndexStorage(config)
    try:
        manifest = manifest_store or ManifestStore(config)
        if reset:
            store.clear()
        manifest.initialize(resolved, reset=reset)

        for video_id, source, checksum, _ in resolved:
            if resume and manifest.completed(
                video_id,
                checksum=checksum,
                config_fingerprint=config.fingerprint(),
            ):
                _report(
                    progress_callback,
                    {
                        "state": "skipped",
                        "stage": "checkpoint",
                        "message": f"Skipping completed video {video_id}.",
                        "video_id": video_id,
                    },
                )
                continue

            _process_video(
                video_id,
                source,
                checksum,
                config,
                store,
                manifest,
                cancellation,
                progress_callback,
                fail_fast=fail_fast,
            )

        return manifest.complete_run(index_size_bytes=store.size_bytes())
    finally:
        if owns_storage:
            store.close()


def run_index(
    sources: Sequence[VideoSource],
    config: IndexConfig,
    *,
    progress_callback: ProgressCallback | None = None,
    cancellation: CancellationToken | None = None,
    resume: bool = True,
    reset: bool = False,
    fail_fast: bool = True,
    storage: IndexStorage | None = None,
    manifest_store: ManifestStore | None = None,
) -> dict[str, Any]:
    with _RunLock(config.run_directory):
        return _run_index_unlocked(
            sources,
            config,
            progress_callback=progress_callback,
            cancellation=cancellation,
            resume=resume,
            reset=reset,
            fail_fast=fail_fast,
            storage=storage,
            manifest_store=manifest_store,
        )


def _video_status(path: Path, source_name: str, checksum: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "source_name": source_name,
        "size": stat.st_size,
        "sha256": checksum,
    }


def index_video(
    path: str,
    progress_callback: ProgressCallback | None = None,
    source_name: str | None = None,
    *,
    config: IndexConfig | None = None,
    cancellation: CancellationToken | None = None,
) -> dict[str, Any]:
    input_path = Path(path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Video not found: {input_path}")
    if not _INDEXING_LOCK.acquire(blocking=False):
        raise IndexingInProgressError("Another video is already being indexed.")

    source = VideoSource(
        path=input_path,
        source_name=source_name or input_path.name,
    )
    checksum = source_checksum(source)
    source = VideoSource(
        path=input_path,
        source_name=source.source_name,
        checksum=checksum,
    )
    active_config = config or IndexConfig.local(video_id=checksum)
    video_id = active_config.video_id or checksum
    video = _video_status(
        input_path,
        source.source_name or input_path.name,
        checksum,
    )
    latest_event: dict[str, Any] = {
        "state": "indexing",
        "stage": "initializing",
    }

    def report(event: dict[str, Any]) -> None:
        latest_event.update(event)
        write_index_status(
            state=event["state"],
            stage=event["stage"],
            message=event["message"],
            video=video,
            current=event.get("current"),
            total=event.get("total"),
            summary=event.get("summary"),
            error=event.get("error"),
        )
        if progress_callback is not None:
            progress_callback(event)

    report(
        {
            "state": "indexing",
            "stage": "initializing",
            "message": (
                "Preparing the selected indexing modalities. "
                "Missing model weights will download before their first use."
            ),
        }
    )
    try:
        manifest = run_index(
            [source],
            active_config,
            progress_callback=report,
            cancellation=cancellation,
            resume=False,
            reset=True,
            fail_fast=True,
        )
        summary = dict(manifest["videos"][video_id]["summary"])
        summary.update(
            {
                "index_schema_version": INDEX_SCHEMA_VERSION,
                "dataset": active_config.dataset,
                "split": active_config.split,
                "run_id": active_config.run_id,
                "video_id": video_id,
                "configuration": active_config.to_dict(),
            }
        )
        report(
            {
                "state": "ready",
                "stage": "complete",
                "message": "Video indexing completed successfully.",
                "summary": summary,
            }
        )
        return summary
    except (IndexCancelledError, KeyboardInterrupt) as exc:
        report(
            {
                "state": "interrupted",
                "stage": latest_event["stage"],
                "message": "Video indexing was cancelled.",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        raise
    except Exception as exc:
        if latest_event.get("state") != "failed":
            report(
                {
                    "state": "failed",
                    "stage": latest_event["stage"],
                    "message": "Video indexing failed.",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        raise
    finally:
        _INDEXING_LOCK.release()
