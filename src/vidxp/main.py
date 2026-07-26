from ast import literal_eval
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from threading import Lock
from typing import Any, Callable

import typer
from rich import print

from vidxp.index_state import (
    IndexingInProgressError,
    IndexNotReadyError,
    fingerprint_file,
    require_ready_index,
    write_index_status,
)

app = typer.Typer()

DEVICE = "cpu"
SENTENCE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
WHISPER_MODEL = "large-v2"
CLIP_MODEL = "ViT-B/32"
COLLECTION_NAMES = (
    "voiceEmbeddings",
    "sceneEmbeddings",
    "actorCollection",
)
INDEXING_DEPENDENCIES = (
    ("ChromaDB", "chromadb"),
    ("CLIP", "clip"),
    ("face recognition", "face_recognition"),
    ("MoviePy", "moviepy.editor"),
    ("NumPy", "numpy"),
    ("OpenCV", "cv2"),
    ("Pillow", "PIL.Image"),
    ("PyTorch", "torch"),
    ("Sentence Transformers", "sentence_transformers"),
    ("WhisperX", "whisperx"),
)

ProgressCallback = Callable[[dict[str, Any]], None]
_INDEXING_LOCK = Lock()


@lru_cache
def get_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(SENTENCE_MODEL, device=DEVICE)


@lru_cache
def get_clip_model():
    import clip

    return clip.load(CLIP_MODEL, device=DEVICE)


@lru_cache
def get_chroma_client():
    import chromadb

    return chromadb.PersistentClient(path="./chroma_data")


def get_collections():
    client = get_chroma_client()
    return tuple(
        client.get_or_create_collection(name=name)
        for name in COLLECTION_NAMES
    )


def reset_collections():
    client = get_chroma_client()
    existing = {
        getattr(collection, "name", collection)
        for collection in client.list_collections()
    }
    for name in COLLECTION_NAMES:
        if name in existing:
            client.delete_collection(name)
    return get_collections()


def _dependency_failures():
    failures = []
    for label, module_name in INDEXING_DEPENDENCIES:
        try:
            import_module(module_name)
        except Exception as exc:
            failures.append((label, f"{type(exc).__name__}: {exc}"))
    return failures


def _require_indexing_dependencies():
    failures = _dependency_failures()
    if failures:
        details = "; ".join(f"{label}: {error}" for label, error in failures)
        raise RuntimeError(f"Indexing dependencies are unavailable: {details}")


class _IndexProgress:
    def __init__(
        self,
        callback: ProgressCallback | None,
        video: dict[str, Any],
    ):
        self.callback = callback
        self.video = video
        self.stage = "initializing"

    def __call__(
        self,
        stage,
        message,
        current=None,
        total=None,
        announce=True,
        *,
        state="indexing",
        summary=None,
        error=None,
    ):
        if state == "indexing":
            self.stage = stage
        event = {
            "state": state,
            "stage": stage,
            "message": message,
            "current": current,
            "total": total,
        }
        if summary is not None:
            event["summary"] = summary
        if error is not None:
            event["error"] = error

        write_index_status(video=self.video, **event)
        if announce:
            print(f"[cyan]{message}[/cyan]")
        if self.callback is not None:
            self.callback(event)


def _should_report_progress(current: int, total: int) -> bool:
    interval = max(total // 100, 1) if total > 0 else 100
    return current == 1 or current == total or current % interval == 0


def _prepare_models(report: _IndexProgress):
    report(
        "preparing_dialogue_model",
        f"Preparing dialogue model: {SENTENCE_MODEL}",
    )
    embedder = get_embedder()

    report(
        "preparing_scene_model",
        f"Preparing scene model: CLIP {CLIP_MODEL}",
    )
    clip_model, preprocess = get_clip_model()
    return embedder, clip_model, preprocess


def _transcribe_audio(input_path: Path, report: _IndexProgress):
    import whisperx
    from moviepy.editor import VideoFileClip

    audio_path = Path("audio.wav")
    report("extracting_audio", "Extracting audio from the video.")
    with VideoFileClip(str(input_path)) as source_video:
        if source_video.audio is None:
            raise ValueError("The selected video does not contain an audio track.")
        source_video.audio.write_audiofile(str(audio_path))

    report(
        "preparing_transcription_model",
        f"Preparing transcription model: WhisperX {WHISPER_MODEL}",
    )
    whisper_model = whisperx.load_model(
        WHISPER_MODEL,
        DEVICE,
        compute_type="float32",
    )
    audio = whisperx.load_audio(str(audio_path))

    report("transcribing_audio", "Transcribing the video audio.")
    transcription = whisper_model.transcribe(audio, batch_size=16)
    language = transcription["language"]
    print(f"[green]Detected audio language: {language}[/green]")

    report(
        "preparing_alignment_model",
        f"Preparing the {language} alignment model.",
    )
    alignment_model, metadata = whisperx.load_align_model(
        language_code=language,
        device=DEVICE,
    )
    report("aligning_audio", "Aligning transcript words to timestamps.")
    aligned = whisperx.align(
        transcription["segments"],
        alignment_model,
        metadata,
        audio,
        DEVICE,
        return_char_alignments=False,
    )
    return aligned["segments"], language


def _index_dialogue(
    segments,
    collection,
    embedder,
    report: _IndexProgress,
) -> int:
    phrases = []
    for segment in segments:
        words = segment["words"]
        for offset in range(0, len(words), 5):
            phrase_words = words[offset:offset + 5]
            phrases.append(
                (
                    " ".join(item["word"] for item in phrase_words),
                    phrase_words[0]["start"],
                )
            )

    total = len(phrases)
    report("dialogue_indexing", "Indexing dialogue phrases.", 0, total)
    for phrase_id, (phrase, start_time) in enumerate(phrases):
        embedding = embedder.encode(phrase, convert_to_tensor=True)
        collection.add(
            ids=[str(phrase_id)],
            embeddings=[embedding.tolist()],
            metadatas=[{"start": start_time}],
        )
        current = phrase_id + 1
        if _should_report_progress(current, total):
            report(
                "dialogue_indexing",
                "Indexing dialogue phrases.",
                current,
                total,
                False,
            )
    return total


def _open_video(path: Path, cv2):
    video = cv2.VideoCapture(str(path))
    fps = video.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        video.release()
        raise ValueError("The selected video has an invalid frame rate.")
    return video, fps, int(video.get(cv2.CAP_PROP_FRAME_COUNT))


def _index_scenes(
    input_path: Path,
    collection,
    clip_model,
    preprocess,
    report: _IndexProgress,
) -> int:
    import cv2
    import torch
    from PIL import Image

    video, fps, total = _open_video(input_path, cv2)
    report("scene_indexing", "Indexing video scenes.", 0, total)
    timestamp = 0.0
    count = 0

    while True:
        retrieved, frame = video.read()
        if not retrieved:
            break

        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image = preprocess(image).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            features = clip_model.encode_image(image)
            features /= features.norm(dim=-1, keepdim=True)

        collection.add(
            ids=[str(count)],
            embeddings=[features.cpu().numpy().tolist()[0]],
            metadatas=[{"time": timestamp}],
        )
        count += 1
        timestamp += 1 / fps
        if _should_report_progress(count, total):
            report(
                "scene_indexing",
                "Indexing video scenes.",
                count,
                total,
                False,
            )

    video.release()
    return count


def _best_face_match(face_recognition, known_encodings, encoding):
    if not known_encodings:
        return None
    distances = face_recognition.face_distance(known_encodings, encoding)
    match = distances.argmin()
    return match if distances[match] < 0.55 else None


def _store_actor_clusters(collection, faces) -> int:
    buckets = {}
    for face in faces:
        buckets.setdefault(face["actor_id"], []).append(face)

    stored = 0
    for actor_id, group in buckets.items():
        if len(group) <= 3:
            continue
        collection.add(
            ids=[actor_id],
            documents=["-"],
            metadatas=[
                {
                    "time": ",".join(str(item["time"]) for item in group),
                    "face_location": ",".join(
                        str(item["face_location"]) for item in group
                    ),
                }
            ],
        )
        stored += 1
    return stored


def _index_actors(
    input_path: Path,
    collection,
    report: _IndexProgress,
) -> tuple[int, int]:
    import cv2
    import face_recognition
    import numpy as np

    video, fps, total = _open_video(input_path, cv2)
    report("actor_indexing", "Detecting and clustering actors.", 0, total)

    known_encodings = []
    known_ids = []
    face_history = {}
    faces = []
    next_id = 1
    frame_index = 0
    timestamp = 0.0

    while True:
        retrieved, frame = video.read()
        if not retrieved:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb_frame)
        encodings = face_recognition.face_encodings(
            rgb_frame,
            locations,
            num_jitters=2,
        )

        for encoding, location in zip(encodings, locations):
            match = _best_face_match(face_recognition, known_encodings, encoding)
            if match is None:
                actor_id = str(next_id)
                next_id += 1
                known_encodings.append(encoding)
                known_ids.append(actor_id)
                face_history[actor_id] = [encoding]
            else:
                actor_id = known_ids[match]
                history = face_history[actor_id]
                history.append(encoding)
                if len(history) > 5:
                    history.pop(0)
                known_encodings[match] = np.mean(history, axis=0)

            faces.append(
                {
                    "time": round(timestamp, 3),
                    "face_location": location,
                    "actor_id": actor_id,
                }
            )

        frame_index += 1
        timestamp += 1 / fps
        if _should_report_progress(frame_index, total):
            report(
                "actor_indexing",
                "Detecting and clustering actors.",
                frame_index,
                total,
                False,
            )

    video.release()
    return frame_index, _store_actor_clusters(collection, faces)


def indexing_in_progress() -> bool:
    return _INDEXING_LOCK.locked()


def index_video(
    path: str,
    progress_callback: ProgressCallback | None = None,
    source_name: str | None = None,
):
    if not _INDEXING_LOCK.acquire(blocking=False):
        raise IndexingInProgressError("Another video is already being indexed.")
    try:
        return _index_video(path, progress_callback, source_name)
    finally:
        _INDEXING_LOCK.release()


def _index_video(
    path: str,
    progress_callback: ProgressCallback | None,
    source_name: str | None,
):
    input_path = Path(path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Video not found: {input_path}")

    video_info = fingerprint_file(input_path)
    video_info["source_name"] = source_name or input_path.name
    report = _IndexProgress(progress_callback, video_info)

    report(
        "initializing",
        "Preparing runtime models. Missing model weights will download before indexing.",
    )
    print("[bold red]Video Indexing...[/bold red]")

    try:
        _require_indexing_dependencies()
        embedder, clip_model, preprocess = _prepare_models(report)
        segments, language = _transcribe_audio(input_path, report)
        report(
            "preparing_index",
            "Clearing any incomplete index and preparing storage.",
        )
        dialogue_store, scene_store, actor_store = reset_collections()
        dialogue_count = _index_dialogue(
            segments,
            dialogue_store,
            embedder,
            report,
        )
        scene_count = _index_scenes(
            input_path,
            scene_store,
            clip_model,
            preprocess,
            report,
        )
        actor_frames, actor_count = _index_actors(
            input_path,
            actor_store,
            report,
        )
        summary = {
            "language": language,
            "dialogue_phrases": dialogue_count,
            "scene_frames": scene_count,
            "actor_frames": actor_frames,
            "actor_clusters": actor_count,
        }
        report(
            "complete",
            "Video indexing completed successfully.",
            announce=False,
            state="ready",
            summary=summary,
        )
        print("[bold green]Video Indexing Complete !!![/bold green]")
        return summary
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        report(
            report.stage,
            f"Indexing failed during {report.stage.replace('_', ' ')}.",
            announce=False,
            state="failed",
            error=error,
        )
        raise


@app.command()
def videoindex(path: str):
    """Index one video. Missing runtime models are downloaded on first use."""
    return index_video(path)


@app.command()
def dialogue(dialogue: str):
    require_ready_index()
    embedder = get_embedder()
    voice_collection, _, _ = get_collections()

    print("[green]Searching dialogue...[/green]")
    query_embedding = embedder.encode(dialogue, convert_to_tensor=True)
    result = voice_collection.query(
        query_embeddings=[query_embedding.tolist()],
        include=["metadatas"],
        n_results=1,
    )
    metadatas = result.get("metadatas") or []
    if not metadatas or not metadatas[0]:
        raise IndexNotReadyError(
            "The completed index contains no searchable dialogue phrases."
        )

    print("[green]Dialogue found !!![/green]")
    return metadatas[0][0]["start"]


@app.command()
def scene(scene: str):
    import clip
    import torch

    require_ready_index()
    clip_model, _ = get_clip_model()
    _, scene_collection, _ = get_collections()

    print("[green]Searching scene...[/green]")
    query = clip.tokenize([scene]).to(DEVICE)
    with torch.no_grad():
        features = clip_model.encode_text(query)
        features /= features.norm(dim=-1, keepdim=True)

    result = scene_collection.query(
        query_embeddings=[features.cpu().numpy().tolist()[0]],
        include=["metadatas"],
        n_results=1,
    )
    metadatas = result.get("metadatas") or []
    if not metadatas or not metadatas[0]:
        raise IndexNotReadyError(
            "The completed index contains no searchable scene frames."
        )

    print("[green]Scene found...[/green]")
    return metadatas[0][0]["time"]


@app.command()
def actor(id: str, input_path: str, output_path: str = "output.mp4"):
    import cv2

    require_ready_index()
    _, _, actor_collection = get_collections()
    metadatas = actor_collection.get(
        ids=[id],
        include=["metadatas"],
    ).get("metadatas") or []
    if not metadatas:
        raise IndexNotReadyError(
            f"Actor cluster {id} was not found in the completed index."
        )

    metadata = metadatas[0]
    times = [float(timestamp) for timestamp in metadata["time"].split(",")]
    face_locations = [
        literal_eval(location + ")")
        if not location.endswith(")")
        else literal_eval(location)
        for location in metadata["face_location"].split("),")
    ]

    video = cv2.VideoCapture(input_path)
    fps = video.get(cv2.CAP_PROP_FPS)
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"avc1"),
        fps,
        (width, height),
    )
    frame_targets = {
        round(timestamp * fps): location
        for timestamp, location in zip(times, face_locations)
    }

    frame_index = 0
    while True:
        retrieved, frame = video.read()
        if not retrieved:
            break
        if frame_index in frame_targets:
            top, right, bottom, left = frame_targets[frame_index]
            color = (0, 255, 0)
            thickness = max(2, int(height / 200))
            font_scale = max(0.5, height / 1000)
            cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)
            cv2.putText(
                frame,
                f"Actor {id}",
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                color,
                thickness,
            )
        writer.write(frame)
        frame_index += 1

    video.release()
    writer.release()
    print(f"[green]Video saved as {output_path}[/green]")


def main():
    try:
        app()
    except (IndexNotReadyError, IndexingInProgressError) as exc:
        print(f"[bold red]{exc}[/bold red]")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
