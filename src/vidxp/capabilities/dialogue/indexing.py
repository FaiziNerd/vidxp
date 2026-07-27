from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from vidxp.capabilities.dialogue.config import dialogue_config
from vidxp.capabilities.dialogue.models import (
    get_alignment_model,
    get_embedder,
    get_whisper_model,
)
from vidxp.core.contracts import (
    CancellationToken,
    IndexConfig,
    StorageRecord,
    VideoSource,
    stable_source_id,
)
from vidxp.core.indexing_common import ProgressCallback, report_progress
from vidxp.core.storage import IndexStorage
from vidxp.core.video import extract_audio


@dataclass(frozen=True)
class DialoguePhrase:
    phrase_id: int
    text: str
    start: float
    end: float


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
    if words_per_phrase <= 0:
        raise ValueError("words_per_phrase must be greater than zero.")
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
        tokens = text.split()
        duration = end - start
        for offset in range(0, len(tokens), words_per_phrase):
            group = tokens[offset:offset + words_per_phrase]
            group_start = start + duration * offset / len(tokens)
            group_end = start + duration * (
                offset + len(group)
            ) / len(tokens)
            phrases.append(
                DialoguePhrase(
                    phrase_id=len(phrases),
                    text=" ".join(group),
                    start=group_start,
                    end=group_end,
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

    settings = dialogue_config(config)
    cancellation.raise_if_cancelled()
    audio_name = hashlib.sha256(
        str(config.video_id).encode("utf-8")
    ).hexdigest()
    audio_path = Path(work_directory) / f"{audio_name}.wav"
    report_progress(
        progress,
        "extracting_audio",
        "Extracting audio from the video.",
    )
    extract_audio(input_path, audio_path)
    try:
        cancellation.raise_if_cancelled()
        report_progress(
            progress,
            "preparing_transcription_model",
            f"Preparing transcription model: WhisperX {settings.whisper_model}.",
        )
        whisper_model = get_whisper_model(
            settings.whisper_model,
            config.device,
        )
        audio = whisperx.load_audio(str(audio_path))
        report_progress(
            progress,
            "transcribing_audio",
            "Transcribing the video audio.",
        )
        transcription = whisper_model.transcribe(
            audio,
            batch_size=settings.transcription_batch_size,
        )
        language = str(transcription["language"])

        cancellation.raise_if_cancelled()
        report_progress(
            progress,
            "preparing_alignment_model",
            f"Preparing the {language} alignment model.",
        )
        alignment_model, alignment_metadata = get_alignment_model(
            language,
            config.device,
        )
        report_progress(
            progress,
            "aligning_audio",
            "Aligning transcript timestamps.",
        )
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


def _dialogue_records(
    phrases,
    vectors,
    config: IndexConfig,
) -> list[StorageRecord]:
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
                    **config.record_identity("dialogue", source_id),
                    "phrase_id": phrase.phrase_id,
                    "text": phrase.text,
                    "start": phrase.start,
                    "end": phrase.end,
                },
            )
        )
    return records


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
    settings = dialogue_config(config)

    language = None
    if source.transcript is not None:
        segments = list(source.transcript)
    else:
        if source.path is None:
            raise ValueError(
                "Dialogue indexing requires a transcript or video path."
            )
        segments, language = transcribe_video(
            source.path,
            config=config,
            work_directory=config.run_directory / "work",
            cancellation=cancellation,
            progress=progress,
        )

    phrases = build_dialogue_phrases(
        segments,
        words_per_phrase=settings.words_per_phrase,
    )
    if not phrases:
        return {"dialogue_phrases": 0, "language": language}

    report_progress(
        progress,
        "preparing_dialogue_model",
        f"Preparing dialogue model: {settings.sentence_model}.",
        0,
        len(phrases),
    )
    encoder = get_embedder(settings.sentence_model, config.device)
    report_progress(
        progress,
        "dialogue_indexing",
        "Indexing dialogue phrases.",
        0,
        len(phrases),
    )
    stored = 0
    for offset in range(0, len(phrases), settings.embedding_batch_size):
        cancellation.raise_if_cancelled()
        group = phrases[offset:offset + settings.embedding_batch_size]
        vectors = encoder.encode(
            [phrase.text for phrase in group],
            batch_size=len(group),
            convert_to_numpy=True,
            normalize_embeddings=settings.normalize_embeddings,
        )
        stored += storage.upsert(
            "dialogue",
            _dialogue_records(group, vectors, config),
            batch_size=config.storage_batch_size,
            cancellation=cancellation,
        )
        report_progress(
            progress,
            "dialogue_indexing",
            "Indexing dialogue phrases.",
            stored,
            len(phrases),
        )
    return {"dialogue_phrases": stored, "language": language}
