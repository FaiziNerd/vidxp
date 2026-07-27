from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from vidxp.core.contracts import (
    CancellationToken,
    IndexConfig,
    StorageRecord,
    batched,
)


def metadata_filter(
    config: IndexConfig,
    *,
    video_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "dataset": config.dataset,
        "split": config.split,
        "run_id": config.run_id,
    }
    if video_id is not None:
        values["video_id"] = video_id
    if extra:
        reserved = set(values) & set(extra)
        if reserved:
            raise ValueError(
                "Search filters cannot override run identity fields: "
                + ", ".join(sorted(reserved))
            )
        values.update(extra)
    clauses = [{key: value} for key, value in values.items()]
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _client_for_path(path: str):
    import chromadb

    return chromadb.PersistentClient(path=path)


class IndexStorage:
    def __init__(self, config: IndexConfig):
        self.config = config
        self.path = config.index_directory
        self.path.mkdir(parents=True, exist_ok=True)
        self.client = _client_for_path(str(self.path.resolve()))
        self._names = dict(zip(("dialogue", "scene", "actor"), config.collection_names))
        self._collections: dict[str, Any] = {}

    def close(self) -> None:
        self._collections.clear()
        close = getattr(self.client, "close", None)
        if close is not None:
            close()

    def __enter__(self) -> "IndexStorage":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def collection(self, modality: str):
        if modality in self._collections:
            return self._collections[modality]
        try:
            name = self._names[modality]
        except KeyError as exc:
            raise ValueError(f"Unsupported collection modality: {modality}") from exc
        collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": self.config.vector_distance},
        )
        configuration = getattr(collection, "configuration", {}) or {}
        actual_distance = (configuration.get("hnsw") or {}).get("space")
        if (
            actual_distance is not None
            and actual_distance != self.config.vector_distance
        ):
            raise ValueError(
                f"Collection {name!r} uses {actual_distance!r} distance, "
                f"not configured {self.config.vector_distance!r} distance."
            )
        self._collections[modality] = collection
        return collection

    def clear(self, modalities: Iterable[str] | None = None) -> None:
        selected = tuple(modalities or self._names)
        existing = {
            getattr(collection, "name", collection)
            for collection in self.client.list_collections()
        }
        for modality in selected:
            name = self._names[modality]
            if name in existing:
                self.client.delete_collection(name)
            self._collections.pop(modality, None)

    def delete_video(self, modality: str, video_id: str) -> None:
        self.collection(modality).delete(
            where=metadata_filter(self.config, video_id=video_id),
        )

    def delete_actor_cluster(self, video_id: str, cluster_id: str) -> None:
        self.collection("actor").delete(
            where=metadata_filter(
                self.config,
                video_id=video_id,
                extra={"cluster_id": cluster_id},
            ),
        )

    def upsert(
        self,
        modality: str,
        records: list[StorageRecord],
        *,
        batch_size: int,
        cancellation: CancellationToken,
    ) -> int:
        if not records:
            return 0
        collection = self.collection(modality)
        stored = 0
        for group in batched(records, batch_size):
            cancellation.raise_if_cancelled()
            if any(record.embedding is None for record in group):
                raise ValueError("Every stored record requires an explicit embedding.")
            options: dict[str, Any] = {
                "ids": [record.source_id for record in group],
                "embeddings": [list(record.embedding or ()) for record in group],
                "metadatas": [dict(record.metadata) for record in group],
            }
            if any(record.document is not None for record in group):
                options["documents"] = [record.document or "" for record in group]
            collection.upsert(**options)
            stored += len(group)
        return stored

    def query(
        self,
        modality: str,
        embedding: list[float],
        *,
        top_k: int,
        video_id: str | None = None,
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        options: dict[str, Any] = {
            "query_embeddings": [embedding],
            "include": ["metadatas", "distances"],
            "n_results": top_k,
            "where": metadata_filter(
                self.config,
                video_id=video_id,
                extra=filters,
            ),
        }
        result = self.collection(modality).query(**options)
        ids = (result.get("ids") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        if not (len(ids) == len(metadatas) == len(distances)):
            raise RuntimeError(
                "The vector store returned misaligned IDs, metadata, and distances."
            )
        return [
            {
                "source_id": source_id,
                "metadata": dict(metadata or {}),
                "raw_distance": float(distance),
            }
            for source_id, metadata, distance in zip(ids, metadatas, distances)
        ]

    def actor_detections(
        self,
        *,
        video_id: str,
        cluster_id: str,
    ) -> list[dict[str, Any]]:
        result = self.collection("actor").get(
            where=metadata_filter(
                self.config,
                video_id=video_id,
                extra={"cluster_id": cluster_id},
            ),
            include=["metadatas"],
        )
        records = [
            dict(metadata)
            for metadata in (result.get("metadatas") or [])
            if metadata
        ]
        return sorted(
            records,
            key=lambda item: (int(item["frame_index"]), item["detection_id"]),
        )

    def size_bytes(self) -> int:
        return directory_size(self.path)


def directory_size(path: str | Path) -> int:
    root = Path(path)
    if not root.exists():
        return 0
    return sum(
        item.stat().st_size
        for item in root.rglob("*")
        if item.is_file()
    )
