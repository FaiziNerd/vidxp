from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from vidxp.core.contracts import (
    IndexConfig,
    IndexSchemaError,
    SearchHit,
    SearchResult,
)
from vidxp.core.models import get_clip_model, get_embedder
from vidxp.core.storage import IndexStorage


REQUIRED_METADATA = {
    "dialogue": {
        "video_id",
        "start",
        "end",
        "text",
        "phrase_id",
        "modality",
    },
    "scene": {
        "video_id",
        "start",
        "end",
        "frame_index",
        "timestamp",
        "fps",
        "duration",
        "modality",
    },
}


def distance_to_score(raw_distance: float) -> float:
    """Map distance to an ordering score without claiming probability.

    Chroma distances are lower-is-better. Negating the raw distance creates a
    strictly monotonic higher-is-better score while retaining the raw value.
    """

    distance = float(raw_distance)
    if not math.isfinite(distance):
        raise ValueError("Search distance must be finite.")
    return -distance


def stable_query_id(query: str, modality: str) -> str:
    digest = hashlib.sha256(f"{modality}\0{query}".encode("utf-8")).hexdigest()
    return f"{modality}:{digest}"


def _dialogue_embedding(query: str, config: IndexConfig) -> list[float]:
    encoder = get_embedder(config.sentence_model, config.device)
    encoded = encoder.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=config.normalize_dialogue_embeddings,
    )
    return encoded[0].tolist()


def _scene_embedding(query: str, config: IndexConfig) -> list[float]:
    import clip
    import torch

    model, _ = get_clip_model(config.clip_model, config.device)
    tokens = clip.tokenize([query]).to(config.device)
    with torch.no_grad():
        features = model.encode_text(tokens)
        features /= features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy().tolist()[0]


def _to_hits(
    modality: str,
    rows: list[dict[str, Any]],
) -> tuple[SearchHit, ...]:
    required = REQUIRED_METADATA[modality]
    ordered = sorted(
        rows,
        key=lambda row: (row["raw_distance"], row["source_id"]),
    )
    hits = []
    for rank, row in enumerate(ordered, start=1):
        metadata = row["metadata"]
        missing = sorted(required - metadata.keys())
        if missing:
            raise IndexSchemaError(
                "The saved index predates the benchmark-ready schema and must "
                f"be rebuilt. Missing {modality} metadata: {', '.join(missing)}."
            )
        start = float(metadata["start"])
        end = float(metadata["end"])
        if start < 0 or end <= start:
            raise IndexSchemaError(
                f"Invalid {modality} interval in {row['source_id']}: "
                f"[{start}, {end}]."
            )
        distance = float(row["raw_distance"])
        hits.append(
            SearchHit(
                rank=rank,
                video_id=str(metadata["video_id"]),
                start=start,
                end=end,
                score=distance_to_score(distance),
                raw_distance=distance,
                modality=modality,
                source_id=str(row["source_id"]),
                metadata=metadata,
            )
        )
    return tuple(hits)


def search(
    query: str,
    modality: str,
    *,
    config: IndexConfig,
    top_k: int = 10,
    video_id: str | None = None,
    query_id: str | None = None,
    filters: Mapping[str, Any] | None = None,
    storage: IndexStorage | None = None,
) -> SearchResult:
    query = query.strip()
    if not query:
        raise ValueError("Search query must not be empty.")
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")
    if modality not in config.enabled_modalities:
        raise ValueError(
            f"The {modality} modality is not present in this index run."
        )
    if modality == "dialogue":
        embedding = _dialogue_embedding(query, config)
    elif modality == "scene":
        embedding = _scene_embedding(query, config)
    else:
        raise ValueError("Semantic search supports dialogue and scene modalities.")

    owns_storage = storage is None
    store = storage or IndexStorage(config)
    try:
        rows = store.query(
            modality,
            embedding,
            top_k=top_k,
            video_id=video_id,
            filters=filters,
        )
    finally:
        if owns_storage:
            store.close()
    return SearchResult(
        query_id=query_id or stable_query_id(query, modality),
        query=query,
        modality=modality,
        hits=_to_hits(modality, rows),
    )


def search_dialogue(query: str, **options: Any) -> SearchResult:
    return search(query, "dialogue", **options)


def search_scene(query: str, **options: Any) -> SearchResult:
    return search(query, "scene", **options)


def serialize_predictions(
    results: list[SearchResult],
    path: str | Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    query_ids = [result.query_id for result in results]
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("Prediction results contain duplicate query IDs.")
    payload = {
        result.query_id: [hit.to_dict() for hit in result.hits]
        for result in sorted(results, key=lambda item: item.query_id)
    }
    if path is not None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return payload
