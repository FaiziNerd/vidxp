from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Mapping, cast

from pydantic import BaseModel

from vidxp.capabilities.contracts import (
    CapabilityContext,
    PreparationContext,
    capability_install_hint,
)
from vidxp.capabilities.registry import (
    capability_names,
    collection_names,
    dependency_checks,
    get_capability,
    index_capability_names,
    preparable_capability_names,
    validate_capability_options,
    validate_capability_names,
)
from vidxp.capabilities.actor.schemas import (
    ActorClusterSummary,
    ActorDetection,
    ActorRenderResult,
)
from vidxp.capabilities.schemas import SearchResult
from vidxp.core.contracts import (
    CancellationToken,
    IndexConfig,
    IndexSchemaError,
)
from vidxp.core.manifest import (
    CHECKPOINT_DIRECTORY,
    COMPLETION_FILE,
    FAILURES_FILE,
    MANIFEST_FILE,
    TIMINGS_FILE,
)
from vidxp.core.runner import (
    ProgressCallback,
    index_video,
    indexing_in_progress,
    local_config_from_status,
)
from vidxp.core.storage import IndexStorage
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
        modalities: Iterable[str] | None = None,
        frame_stride: int = 1,
        capability_options: Mapping[
            str,
            Mapping[str, Any],
        ] | None = None,
        progress_callback: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
        source_name: str | None = None,
    ) -> dict[str, Any]:
        selected = self._validate_modalities(
            index_capability_names() if modalities is None else modalities
        )
        non_indexable = [
            name
            for name in selected
            if get_capability(name).indexer is None
        ]
        if non_indexable:
            raise ValueError(
                "These capabilities do not support indexing: "
                + ", ".join(non_indexable)
            )
        options: dict[str, Any] = {
            "enabled_modalities": selected,
            "frame_stride": frame_stride,
            "storage_directory": self.index_directory,
            "collection_names": collection_names(selected),
            "capability_options": validate_capability_options(
                selected,
                capability_options,
            ),
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
        modalities: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        selected = self._validate_modalities(
            capability_names() if modalities is None else modalities
        )
        checks = list(dependency_checks(selected))
        return {
            "ok": all(check["ok"] for check in checks),
            "modalities": list(selected),
            "checks": checks,
        }

    def prepare_models(
        self,
        modalities: Iterable[str] | None = None,
        *,
        capability_options: Mapping[
            str,
            Mapping[str, Any],
        ] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        selected = self._validate_modalities(
            preparable_capability_names()
            if modalities is None
            else modalities
        )
        options = validate_capability_options(selected, capability_options)
        checks = dependency_checks(selected)
        failures = [check for check in checks if not check["ok"]]
        if failures:
            details = "; ".join(
                f"{check['name']}: {check['error']}"
                for check in failures
            )
            extras = ",".join(
                get_capability(name).extra for name in selected
            )
            raise RuntimeError(
                f"{details}. {capability_install_hint(extras)}"
            )

        prepared = []
        for name in selected:
            capability = get_capability(name)
            prepare = capability.prepare
            if prepare is not None:
                prepared.extend(
                    prepare(
                        PreparationContext(
                            device=self.device or "cpu",
                            settings=capability.config_model.model_validate(
                                options[name]
                            ),
                        ),
                        progress_callback,
                    )
                )
        return {
            "prepared": prepared,
            "modalities": list(selected),
            "device": self.device or "cpu",
        }

    def execute(
        self,
        capability: str,
        operation: str,
        payload: BaseModel | Mapping[str, Any],
    ) -> BaseModel:
        """Validate and execute a registered capability operation."""

        definition = get_capability(capability)
        try:
            selected_operation = definition.operations[operation]
        except KeyError as exc:
            available = ", ".join(definition.operations) or "none"
            raise ValueError(
                f"Capability {capability!r} has no operation {operation!r}. "
                f"Available operations: {available}."
            ) from exc
        config = None
        if selected_operation.requires_index:
            config, _ = self.active_config()
            if capability not in config.enabled_modalities:
                raise ValueError(
                    f"The {capability} capability is not present in this index."
                )
        return selected_operation.invoke(
            CapabilityContext(config=config),
            payload,
        )

    def search(
        self,
        modality: str,
        query: str,
        *,
        top_k: int = 10,
    ) -> SearchResult:
        return cast(
            SearchResult,
            self.execute(
                modality,
                "search",
                {"query": query, "top_k": top_k},
            ),
        )

    def actor_clusters(self) -> tuple[ActorClusterSummary, ...]:
        result = self.execute("actor", "clusters", {})
        return tuple(result.clusters)

    def actor_detections(
        self,
        cluster_id: str,
    ) -> list[ActorDetection]:
        result = self.execute(
            "actor",
            "detections",
            {"cluster_id": cluster_id},
        )
        return list(result.detections)

    def render_actor(
        self,
        cluster_id: str,
        input_path: str | Path,
        output_path: str | Path,
    ) -> ActorRenderResult:
        return cast(
            ActorRenderResult,
            self.execute(
                "actor",
                "render",
                {
                    "cluster_id": cluster_id,
                    "input_path": input_path,
                    "output_path": output_path,
                },
            ),
        )

    def clear_index(self) -> bool:
        if not self.index_directory.exists():
            return False
        base_config = IndexConfig.local(
            storage_directory=self.index_directory,
            enabled_modalities=index_capability_names(),
            collection_names=collection_names(),
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
    def _validate_modalities(
        modalities: Iterable[str],
    ) -> tuple[str, ...]:
        return validate_capability_names(modalities)
