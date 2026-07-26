from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping, Sequence

from vidxp.core.contracts import (
    CancellationToken,
    IndexConfig,
    StorageRecord,
    VideoSource,
    batched,
    stable_source_id,
)
from vidxp.core.models import (
    get_alignment_model,
    get_clip_model,
    get_embedder,
    get_whisper_model,
)
from vidxp.core.storage import IndexStorage
from vidxp.core.video import (
    FrameSample,
    FrameStreamStats,
    extract_audio,
    iter_frame_batches,
    probe_video,
)


ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class DialoguePhrase:
    phrase_id: int
    text: str
    start: float
    end: float


def _progress(
    callback: ProgressCallback | None,
    stage: str,
    message: str,
    current: int | None = None,
    total: int | None = None,
) -> None:
    if callback is not None:
        callback(
            {
                "state": "indexing",
                "stage": stage,
                "message": message,
                "current": current,
                "total": total,
            }
        )


def _valid_interval(start: Any, end: Any, label: str) -> tuple[float, float]:
    start_value = float(start)
    end_value = float(end)
    if start_value < 0 or end_value <= start_value:
        raise ValueError(
            f"{label} must have a non-negative, non-zero interval; "
            f"received [{start_value}, {end_value}]."
        )
    return start_value, end_value


def build_dialogue_phrases(
    segments: Sequence[Mapping[str, Any]],
    *,
    words_per_phrase: int,
) -> list[DialoguePhrase]:
    phrases: list[DialoguePhrase] = []
    for segment_index, segment in enumerate(segments):
        words = segment.get("words") or []
        if words:
            timestamped = [
                word
                for word in words
                if str(word.get("word", word.get("text", ""))).strip()
                and word.get("start") is not None
                and word.get("end") is not None
            ]
            for offset in range(0, len(timestamped), words_per_phrase):
                group = timestamped[offset:offset + words_per_phrase]
                if not group:
                    continue
                start, end = _valid_interval(
                    group[0]["start"],
                    group[-1]["end"],
                    f"Transcript word group in segment {segment_index}",
                )
                text = " ".join(
                    str(word.get("word", word.get("text", ""))).strip()
                    for word in group
                )
                phrases.append(
                    DialoguePhrase(
                        phrase_id=len(phrases),
                        text=text,
                        start=start,
                        end=end,
                    )
                )
            continue

        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        if segment.get("start") is None or segment.get("end") is None:
            raise ValueError(
                f"Transcript segment {segment_index} lacks start/end timestamps."
            )
        start, end = _valid_interval(
            segment["start"],
            segment["end"],
            f"Transcript segment {segment_index}",
        )
        phrases.append(
            DialoguePhrase(
                phrase_id=len(phrases),
                text=text,
                start=start,
                end=end,
            )
        )
    return phrases


def transcribe_video(
    input_path: str | Path,
    *,
    config: IndexConfig,
    work_directory: str | Path,
    cancellation: CancellationToken,
    progress: ProgressCallback | None,
) -> tuple[list[Mapping[str, Any]], str]:
    import whisperx

    cancellation.raise_if_cancelled()
    audio_name = hashlib.sha256(
        str(config.video_id).encode("utf-8")
    ).hexdigest()
    audio_path = Path(work_directory) / f"{audio_name}.wav"
    _progress(progress, "extracting_audio", "Extracting audio from the video.")
    extract_audio(input_path, audio_path)
    try:
        cancellation.raise_if_cancelled()
        _progress(
            progress,
            "preparing_transcription_model",
            f"Preparing transcription model: WhisperX {config.whisper_model}.",
        )
        whisper_model = get_whisper_model(config.whisper_model, config.device)
        audio = whisperx.load_audio(str(audio_path))
        _progress(progress, "transcribing_audio", "Transcribing the video audio.")
        transcription = whisper_model.transcribe(
            audio,
            batch_size=config.transcription_batch_size,
        )
        language = str(transcription["language"])

        cancellation.raise_if_cancelled()
        _progress(
            progress,
            "preparing_alignment_model",
            f"Preparing the {language} alignment model.",
        )
        alignment_model, alignment_metadata = get_alignment_model(
            language,
            config.device,
        )
        _progress(progress, "aligning_audio", "Aligning transcript timestamps.")
        aligned = whisperx.align(
            transcription["segments"],
            alignment_model,
            alignment_metadata,
            audio,
            config.device,
            return_char_alignments=False,
        )
        return list(aligned["segments"]), language
    finally:
        audio_path.unlink(missing_ok=True)


def index_dialogue(
    source: VideoSource,
    *,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    if config.video_id is None:
        raise ValueError("IndexConfig.video_id is required for indexing.")

    language = None
    if source.transcript is not None:
        segments = list(source.transcript)
    else:
        if source.path is None:
            raise ValueError("Dialogue indexing requires a transcript or video path.")
        segments, language = transcribe_video(
            source.path,
            config=config,
            work_directory=config.run_directory / "work",
            cancellation=cancellation,
            progress=progress,
        )

    phrases = build_dialogue_phrases(
        segments,
        words_per_phrase=config.dialogue_words_per_phrase,
    )
    _progress(
        progress,
        "preparing_dialogue_model",
        f"Preparing dialogue model: {config.sentence_model}.",
        0,
        len(phrases),
    )
    encoder = get_embedder(config.sentence_model, config.device)
    _progress(
        progress,
        "dialogue_indexing",
        "Indexing dialogue phrases.",
        0,
        len(phrases),
    )
    stored = 0
    for offset in range(0, len(phrases), config.dialogue_batch_size):
        cancellation.raise_if_cancelled()
        group = phrases[offset:offset + config.dialogue_batch_size]
        vectors = encoder.encode(
            [phrase.text for phrase in group],
            batch_size=len(group),
            convert_to_numpy=True,
            normalize_embeddings=config.normalize_dialogue_embeddings,
        )
        records = _dialogue_records(group, vectors, config)
        stored += storage.upsert(
            "dialogue",
            records,
            batch_size=config.storage_batch_size,
            cancellation=cancellation,
        )
        _progress(
            progress,
            "dialogue_indexing",
            "Indexing dialogue phrases.",
            stored,
            len(phrases),
        )
    return {"dialogue_phrases": stored, "language": language}


def _dialogue_records(phrases, vectors, config: IndexConfig):
    records = []
    for phrase, vector in zip(phrases, vectors):
        source_id = stable_source_id(
            config.run_id,
            str(config.video_id),
            "dialogue",
            f"p{phrase.phrase_id:08d}",
        )
        records.append(
            StorageRecord(
                source_id=source_id,
                embedding=vector.tolist(),
                document=phrase.text,
                metadata={
                    "dataset": config.dataset,
                    "split": config.split,
                    "run_id": config.run_id,
                    "video_id": config.video_id,
                    "modality": "dialogue",
                    "source_id": source_id,
                    "phrase_id": phrase.phrase_id,
                    "text": phrase.text,
                    "start": phrase.start,
                    "end": phrase.end,
                },
            )
        )
    return records


def _encode_scene_batch(samples, model, preprocess, device):
    import torch
    from PIL import Image

    images = torch.stack(
        [preprocess(Image.fromarray(sample.frame)) for sample in samples]
    ).to(device)
    with torch.no_grad():
        features = model.encode_image(images)
        features /= features.norm(dim=-1, keepdim=True)
    return features.cpu().numpy().tolist()


def _scene_records(samples, vectors, info, config: IndexConfig):
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
                    "dataset": config.dataset,
                    "split": config.split,
                    "run_id": config.run_id,
                    "video_id": config.video_id,
                    "modality": "scene",
                    "source_id": source_id,
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


@dataclass
class ActorIndexState:
    known_encodings: list[Any] = field(default_factory=list)
    known_ids: list[str] = field(default_factory=list)
    histories: dict[str, list[Any]] = field(default_factory=dict)
    cluster_sizes: dict[str, int] = field(default_factory=dict)
    processed_frames: int = 0


@dataclass
class SceneIndexState:
    model: Any
    preprocess: Any
    stored_frames: int = 0


def _actor_records(detections, config: IndexConfig):
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
                    "dataset": config.dataset,
                    "split": config.split,
                    "run_id": config.run_id,
                    "video_id": config.video_id,
                    "modality": "actor",
                    "source_id": source_id,
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


def _process_actor_samples(
    samples,
    *,
    state: ActorIndexState,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
) -> None:
    import face_recognition
    import numpy as np

    for group in batched(samples, config.actor_batch_size):
        cancellation.raise_if_cancelled()
        detections = []
        for sample in group:
            cancellation.raise_if_cancelled()
            locations = face_recognition.face_locations(sample.frame)
            encodings = face_recognition.face_encodings(
                sample.frame,
                locations,
                num_jitters=config.face_num_jitters,
            )
            for ordinal, (encoding, location) in enumerate(
                zip(encodings, locations)
            ):
                match = _best_face_match(
                    face_recognition,
                    state.known_encodings,
                    encoding,
                    config.face_match_threshold,
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


def _finalize_actor_index(
    state: ActorIndexState,
    *,
    config: IndexConfig,
    storage: IndexStorage,
) -> tuple[int, int]:
    rejected = [
        cluster_id
        for cluster_id, size in state.cluster_sizes.items()
        if size < config.actor_min_detections
    ]
    for cluster_id in rejected:
        storage.delete_actor_cluster(str(config.video_id), cluster_id)
    retained = {
        cluster_id: size
        for cluster_id, size in state.cluster_sizes.items()
        if size >= config.actor_min_detections
    }
    return sum(retained.values()), len(retained)


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


def _process_scene_samples(
    samples,
    *,
    state: SceneIndexState,
    info,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
) -> None:
    for group in batched(samples, config.scene_batch_size):
        cancellation.raise_if_cancelled()
        vectors = _encode_scene_batch(
            group,
            state.model,
            state.preprocess,
            config.device,
        )
        state.stored_frames += storage.upsert(
            "scene",
            _scene_records(group, vectors, info, config),
            batch_size=config.storage_batch_size,
            cancellation=cancellation,
        )


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
            _process_scene_samples(
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
            _process_actor_samples(
                rgb_samples,
                state=actor_state,
                config=config,
                storage=storage,
                cancellation=cancellation,
            )
            timings["actor"] += perf_counter() - actor_started

        _progress(
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
    timings: Mapping[str, float],
    started: float,
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
        "_timings": {
            **timings,
            "visual_total": perf_counter() - started,
        },
    }


def index_visuals(
    source: VideoSource,
    *,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
    progress: ProgressCallback | None = None,
    modalities: Sequence[str] | None = None,
) -> dict[str, Any]:
    if config.video_id is None:
        raise ValueError("IndexConfig.video_id is required for indexing.")
    if source.path is None:
        raise ValueError("Scene and actor indexing require a video path.")

    selected = tuple(
        modality
        for modality in (modalities or config.enabled_modalities)
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
        _progress(
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

    _progress(
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
        actor_detections, actor_clusters = _finalize_actor_index(
            actor_state,
            config=config,
            storage=storage,
        )
        timings["actor"] += perf_counter() - actor_started

    return _visual_summary(
        scene_state=scene_state,
        actor_state=actor_state,
        stream_stats=stream_stats,
        actor_detections=actor_detections,
        actor_clusters=actor_clusters,
        info=info,
        timings=timings,
        started=started,
    )


def index_scenes(source: VideoSource, **options: Any) -> dict[str, Any]:
    return index_visuals(source, modalities=("scene",), **options)


def index_actors(source: VideoSource, **options: Any) -> dict[str, Any]:
    return index_visuals(source, modalities=("actor",), **options)


INDEXERS = {
    "dialogue": index_dialogue,
    "scene": index_scenes,
    "actor": index_actors,
    "visual": index_visuals,
}
