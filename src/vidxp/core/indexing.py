from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from vidxp.core.contracts import (
    CancellationToken,
    IndexConfig,
    StorageRecord,
    VideoSource,
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
    import cv2
    import torch
    from PIL import Image

    images = torch.stack(
        [
            preprocess(
                Image.fromarray(
                    cv2.cvtColor(sample.frame, cv2.COLOR_BGR2RGB)
                )
            )
            for sample in samples
        ]
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


def index_scenes(
    source: VideoSource,
    *,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    if config.video_id is None:
        raise ValueError("IndexConfig.video_id is required for indexing.")
    if source.path is None:
        raise ValueError("Scene indexing requires a video path.")

    info = probe_video(source.path)
    _progress(
        progress,
        "preparing_scene_model",
        f"Preparing scene model: CLIP {config.clip_model}.",
    )
    model, preprocess = get_clip_model(config.clip_model, config.device)
    expected = (info.frame_count + config.frame_stride - 1) // config.frame_stride
    _progress(progress, "scene_indexing", "Indexing sampled video frames.", 0, expected)
    stored = 0
    for samples in iter_frame_batches(
        source.path,
        frame_stride=config.frame_stride,
        batch_size=config.scene_batch_size,
        cancellation=cancellation,
    ):
        cancellation.raise_if_cancelled()
        vectors = _encode_scene_batch(
            samples,
            model,
            preprocess,
            config.device,
        )
        records = _scene_records(samples, vectors, info, config)
        stored += storage.upsert(
            "scene",
            records,
            batch_size=config.storage_batch_size,
            cancellation=cancellation,
        )
        _progress(
            progress,
            "scene_indexing",
            "Indexing sampled video frames.",
            stored,
            expected,
        )
    return {
        "scene_frames": stored,
        "decoded_frames": info.frame_count,
        "duration": info.duration,
        "fps": info.fps,
    }


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


def _cluster_actor_detections(
    source: VideoSource,
    *,
    config: IndexConfig,
    cancellation: CancellationToken,
    progress: ProgressCallback | None,
):
    import cv2
    import face_recognition
    import numpy as np

    info = probe_video(source.path)
    expected = (info.frame_count + config.frame_stride - 1) // config.frame_stride
    _progress(
        progress,
        "actor_indexing",
        "Detecting and clustering actors.",
        0,
        expected,
    )
    known_encodings = []
    known_ids: list[str] = []
    histories: dict[str, list[Any]] = {}
    detections: list[dict[str, Any]] = []
    processed = 0

    for samples in iter_frame_batches(
        source.path,
        frame_stride=config.frame_stride,
        batch_size=config.actor_batch_size,
        cancellation=cancellation,
    ):
        cancellation.raise_if_cancelled()
        for sample in samples:
            rgb_frame = cv2.cvtColor(sample.frame, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(rgb_frame)
            encodings = face_recognition.face_encodings(
                rgb_frame,
                locations,
                num_jitters=config.face_num_jitters,
            )
            for ordinal, (encoding, location) in enumerate(
                zip(encodings, locations)
            ):
                match = _best_face_match(
                    face_recognition,
                    known_encodings,
                    encoding,
                    config.face_match_threshold,
                )
                if match is None:
                    cluster_id = str(len(known_ids) + 1)
                    known_ids.append(cluster_id)
                    known_encodings.append(encoding)
                    histories[cluster_id] = [encoding]
                else:
                    cluster_id = known_ids[match]
                    history = histories[cluster_id]
                    history.append(encoding)
                    if len(history) > 5:
                        history.pop(0)
                    known_encodings[match] = np.mean(history, axis=0)
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
            processed += 1
        _progress(
            progress,
            "actor_indexing",
            "Detecting and clustering actors.",
            processed,
            expected,
        )
    return info, processed, detections


def _actor_records(detections, config: IndexConfig):
    cluster_sizes: dict[str, int] = {}
    for detection in detections:
        cluster_id = detection["cluster_id"]
        cluster_sizes[cluster_id] = cluster_sizes.get(cluster_id, 0) + 1
    retained = [
        detection
        for detection in detections
        if cluster_sizes[detection["cluster_id"]]
        >= config.actor_min_detections
    ]
    records = []
    for detection in retained:
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
    return records, retained


def index_actors(
    source: VideoSource,
    *,
    config: IndexConfig,
    storage: IndexStorage,
    cancellation: CancellationToken,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    if config.video_id is None:
        raise ValueError("IndexConfig.video_id is required for indexing.")
    if source.path is None:
        raise ValueError("Actor indexing requires a video path.")

    info, processed, detections = _cluster_actor_detections(
        source,
        config=config,
        cancellation=cancellation,
        progress=progress,
    )
    records, retained = _actor_records(detections, config)
    stored = storage.upsert(
        "actor",
        records,
        batch_size=config.storage_batch_size,
        cancellation=cancellation,
    )
    return {
        "actor_frames": processed,
        "actor_decoded_frames": info.frame_count,
        "actor_detections": stored,
        "actor_clusters": len(
            {detection["cluster_id"] for detection in retained}
        ),
    }


INDEXERS = {
    "dialogue": index_dialogue,
    "scene": index_scenes,
    "actor": index_actors,
}
