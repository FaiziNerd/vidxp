from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from vidxp.core.actor_results import (
    ActorClusterSummary,
    ActorRenderResult,
    actor_clusters,
    actor_detections,
    render_actor_result,
)
from vidxp.core.contracts import (
    SUPPORTED_MODALITIES,
    CancellationToken,
    IndexConfig,
    SearchResult,
)
from vidxp.core.manifest import (
    CHECKPOINT_DIRECTORY,
    COMPLETION_FILE,
    FAILURES_FILE,
    MANIFEST_FILE,
    TIMINGS_FILE,
)
from vidxp.core.models import (
    INDEXING_DEPENDENCIES,
    dependency_failures,
    get_alignment_model,
    get_clip_model,
    get_embedder,
    get_whisper_model,
)
from vidxp.core.runner import (
    ProgressCallback,
    index_video,
    indexing_in_progress,
    local_config_from_status,
)
from vidxp.core.search import search_dialogue, search_scene
from vidxp.core.storage import IndexStorage
from vidxp.core.video import ffmpeg_binary
from vidxp.index_state import (
    INDEX_STATUS_FILE,
    INDEX_STATUS_SCHEMA,
    IndexingInProgressError,
    read_index_status,
    require_ready_index,
)


class VidXPService:
    """Reusable application boundary for CLI, HTTP, and other adapters."""

    def __init__(
        self,
        index_directory: str | Path = "chroma_data",
        *,
        device: str | None = None,
    ) -> None:
        self.index_directory = Path(index_directory)
        self.device = device

    def index_status(self) -> dict[str, Any]:
        status = read_index_status(self.index_directory)
        if status is not None:
            payload = dict(status)
        else:
            payload = {
                "schema_version": INDEX_STATUS_SCHEMA,
                "state": "missing",
                "stage": "status",
                "message": "No local video index was found.",
            }
        payload["index_directory"] = str(self.index_directory)
        return payload

    def active_config(self) -> tuple[IndexConfig, dict[str, Any]]:
        status = require_ready_index(self.index_directory)
        config = local_config_from_status(
            status,
            storage_directory=self.index_directory,
        )
        if self.device is not None:
            config = replace(config, device=self.device)
        return config, status

    def create_index(
        self,
        video_path: str | Path,
        *,
        modalities: Iterable[str] = SUPPORTED_MODALITIES,
        frame_stride: int = 1,
        progress_callback: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
        source_name: str | None = None,
    ) -> dict[str, Any]:
        selected = tuple(dict.fromkeys(str(item) for item in modalities))
        options: dict[str, Any] = {
            "enabled_modalities": selected,
            "frame_stride": frame_stride,
            "storage_directory": self.index_directory,
        }
        if self.device is not None:
            options["device"] = self.device
        config = IndexConfig.local(**options)
        return index_video(
            str(video_path),
            progress_callback=progress_callback,
            source_name=source_name,
            config=config,
            cancellation=cancellation,
        )

    def indexing_in_progress(self) -> bool:
        options: dict[str, Any] = {
            "storage_directory": self.index_directory,
        }
        if self.device is not None:
            options["device"] = self.device
        return indexing_in_progress(IndexConfig.local(**options))

    def check_dependencies(
        self,
        modalities: Iterable[str] = SUPPORTED_MODALITIES,
    ) -> dict[str, Any]:
        selected = self._validate_modalities(modalities)
        failures = dict(
            dependency_failures(
                selected,
                needs_transcription="dialogue" in selected,
            )
        )
        dependencies = []
        for modality in selected:
            dependencies.extend(INDEXING_DEPENDENCIES[modality])
        if "dialogue" in selected:
            dependencies.extend(INDEXING_DEPENDENCIES["transcription"])

        checks = []
        seen = set()
        for dependency in dependencies:
            if dependency.label in seen:
                continue
            seen.add(dependency.label)
            error = failures.get(dependency.label)
            checks.append(
                {
                    "name": dependency.label,
                    "ok": error is None,
                    "error": error,
                }
            )
        if "dialogue" in selected:
            try:
                resolved_ffmpeg = ffmpeg_binary()
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                failures["FFmpeg"] = error
                checks.append(
                    {"name": "FFmpeg", "ok": False, "error": error}
                )
            else:
                checks.append(
                    {
                        "name": "FFmpeg",
                        "ok": True,
                        "path": resolved_ffmpeg,
                        "error": None,
                    }
                )
        return {
            "ok": not failures,
            "modalities": list(selected),
            "checks": checks,
        }

    def prepare_models(
        self,
        modalities: Iterable[str] = ("dialogue", "scene"),
        *,
        language: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        selected = self._validate_modalities(modalities)
        config = IndexConfig.local(
            enabled_modalities=selected,
            device=self.device or "cpu",
            storage_directory=self.index_directory,
        )
        failures = dependency_failures(
            selected,
            needs_transcription="dialogue" in selected,
        )
        if failures:
            details = "; ".join(
                f"{label}: {error}" for label, error in failures
            )
            raise RuntimeError(details)

        prepared = []

        def report(stage: str, message: str) -> None:
            if progress_callback is not None:
                progress_callback(
                    {
                        "state": "preparing",
                        "stage": stage,
                        "message": message,
                    }
                )

        if "dialogue" in selected:
            report(
                "dialogue_model",
                f"Preparing dialogue model: {config.sentence_model}",
            )
            get_embedder(config.sentence_model, config.device)
            prepared.append(config.sentence_model)
            report(
                "transcription_model",
                f"Preparing transcription model: WhisperX "
                f"{config.whisper_model}",
            )
            get_whisper_model(config.whisper_model, config.device)
            prepared.append(config.whisper_model)
            if language:
                report(
                    "alignment_model",
                    f"Preparing the {language} alignment model.",
                )
                get_alignment_model(language, config.device)
                prepared.append(f"whisperx-alignment:{language}")
        if "scene" in selected:
            report(
                "scene_model",
                f"Preparing scene model: CLIP {config.clip_model}",
            )
            get_clip_model(config.clip_model, config.device)
            prepared.append(config.clip_model)
        return {
            "prepared": prepared,
            "modalities": list(selected),
            "device": config.device,
            "language": language,
        }

    def search(
        self,
        modality: str,
        query: str,
        *,
        top_k: int = 10,
    ) -> SearchResult:
        config, _ = self.active_config()
        if modality not in config.enabled_modalities:
            raise ValueError(
                f"The {modality} modality is not present in this index."
            )
        find = {
            "dialogue": search_dialogue,
            "scene": search_scene,
        }.get(modality)
        if find is None:
            raise ValueError(
                "Semantic search supports dialogue and scene modalities."
            )
        return find(
            query,
            config=config,
            top_k=top_k,
            video_id=config.video_id,
        )

    def actor_clusters(self) -> tuple[ActorClusterSummary, ...]:
        config, _ = self.active_config()
        self._require_actor(config)
        return actor_clusters(config)

    def actor_detections(self, cluster_id: str) -> list[dict[str, Any]]:
        config, _ = self.active_config()
        self._require_actor(config)
        return actor_detections(config, cluster_id)

    def render_actor(
        self,
        cluster_id: str,
        input_path: str | Path,
        output_path: str | Path,
    ) -> ActorRenderResult:
        config, _ = self.active_config()
        self._require_actor(config)
        return render_actor_result(
            config,
            cluster_id,
            input_path,
            output_path,
        )

    def clear_index(self) -> bool:
        if not self.index_directory.exists():
            return False
        base_config = IndexConfig.local(
            storage_directory=self.index_directory,
        )
        if indexing_in_progress(base_config):
            raise IndexingInProgressError(
                f"Indexing is active for {self.index_directory}."
            )

        status = read_index_status(self.index_directory)
        if status is not None and status.get("state") == "ready":
            try:
                config = local_config_from_status(
                    status,
                    storage_directory=self.index_directory,
                )
            except (IndexSchemaError, KeyError, TypeError, ValueError):
                config = base_config
        else:
            config = base_config
        with IndexStorage(config) as storage:
            storage.clear()

        for name in (
            INDEX_STATUS_FILE,
            MANIFEST_FILE,
            TIMINGS_FILE,
            FAILURES_FILE,
            COMPLETION_FILE,
        ):
            (self.index_directory / name).unlink(missing_ok=True)
        checkpoint_directory = self.index_directory / CHECKPOINT_DIRECTORY
        if checkpoint_directory.is_dir():
            for checkpoint in checkpoint_directory.glob("*.json"):
                checkpoint.unlink()
            try:
                checkpoint_directory.rmdir()
            except OSError:
                pass
        return True

    @staticmethod
    def _require_actor(config: IndexConfig) -> None:
        if "actor" not in config.enabled_modalities:
            raise ValueError("The actor modality is not present in this index.")

    @staticmethod
    def _validate_modalities(
        modalities: Iterable[str],
    ) -> tuple[str, ...]:
        selected = tuple(dict.fromkeys(str(item) for item in modalities))
        IndexConfig(enabled_modalities=selected)
        return selected
