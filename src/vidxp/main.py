from ast import literal_eval
from functools import lru_cache
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
    chroma_client = get_chroma_client()
    return (
        chroma_client.get_or_create_collection(name=COLLECTION_NAMES[0]),
        chroma_client.get_or_create_collection(name=COLLECTION_NAMES[1]),
        chroma_client.get_or_create_collection(name=COLLECTION_NAMES[2]),
    )


def reset_collections():
    chroma_client = get_chroma_client()
    existing = {
        getattr(collection, "name", collection)
        for collection in chroma_client.list_collections()
    }
    for collection_name in COLLECTION_NAMES:
        if collection_name in existing:
            chroma_client.delete_collection(collection_name)
    return get_collections()


def _report_progress(
    callback: ProgressCallback | None,
    *,
    stage: str,
    message: str,
    video: dict[str, Any],
    current: int | None = None,
    total: int | None = None,
    announce: bool = True,
):
    event = {
        "stage": stage,
        "message": message,
        "current": current,
        "total": total,
    }
    write_index_status(
        state="indexing",
        stage=stage,
        message=message,
        video=video,
        current=current,
        total=total,
    )
    if announce:
        print(f"[cyan]{message}[/cyan]")
    if callback is not None:
        callback(event)


def _should_report_progress(current: int, total: int) -> bool:
    interval = max(total // 100, 1) if total > 0 else 100
    return current == 1 or current == total or current % interval == 0


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
    current_stage = "initializing"

    def report(
        stage: str,
        message: str,
        current: int | None = None,
        total: int | None = None,
        announce: bool = True,
    ):
        nonlocal current_stage
        current_stage = stage
        _report_progress(
            progress_callback,
            stage=stage,
            message=message,
            video=video_info,
            current=current,
            total=total,
            announce=announce,
        )

    report(
        "initializing",
        "Preparing runtime models. Missing model weights will download before indexing.",
    )
    print("[bold red]Video Indexing...[/bold red]")

    try:
        import cv2
        import face_recognition
        import numpy as np
        import torch
        import whisperx
        from moviepy.editor import VideoFileClip
        from PIL import Image

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

        report(
            "preparing_index",
            "Clearing any incomplete index and preparing storage.",
        )
        voice_collection, scene_collection, actor_collection = reset_collections()

        report("extracting_audio", "Extracting audio from the video.")
        audio_path = Path("audio.wav")
        with VideoFileClip(str(input_path)) as source_video:
            if source_video.audio is None:
                raise ValueError("The selected video does not contain an audio track.")
            source_video.audio.write_audiofile(str(audio_path))

        batch_size = 16
        compute_type = "float32"

        report(
            "preparing_transcription_model",
            f"Preparing transcription model: WhisperX {WHISPER_MODEL}",
        )
        whisper_model = whisperx.load_model(
            WHISPER_MODEL,
            DEVICE,
            compute_type=compute_type,
        )
        audio = whisperx.load_audio(str(audio_path))

        report("transcribing_audio", "Transcribing the video audio.")
        result = whisper_model.transcribe(audio, batch_size=batch_size)
        detected_language = result["language"]
        print(f"[green]Detected audio language: {detected_language}[/green]")

        report(
            "preparing_alignment_model",
            f"Preparing the {detected_language} alignment model.",
        )
        model_a, metadata = whisperx.load_align_model(
            language_code=detected_language,
            device=DEVICE,
        )

        report("aligning_audio", "Aligning transcript words to timestamps.")
        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio,
            DEVICE,
            return_char_alignments=False,
        )

        phrase_length = 5
        phrases = []
        for segment in result["segments"]:
            words = segment["words"]
            for offset in range(0, len(words), phrase_length):
                phrase_segments = words[offset:offset + phrase_length]
                phrases.append(
                    (
                        " ".join(item["word"] for item in phrase_segments),
                        phrase_segments[0]["start"],
                    )
                )

        phrase_total = len(phrases)
        report(
            "dialogue_indexing",
            "Indexing dialogue phrases.",
            current=0,
            total=phrase_total,
        )
        for phrase_id, (phrase, start_time) in enumerate(phrases):
            print(phrase)
            print(start_time)
            embedding = embedder.encode(phrase, convert_to_tensor=True)
            voice_collection.add(
                ids=[str(phrase_id)],
                embeddings=[embedding.tolist()],
                metadatas=[{"start": start_time}],
            )
            current = phrase_id + 1
            if _should_report_progress(current, phrase_total):
                report(
                    "dialogue_indexing",
                    "Indexing dialogue phrases.",
                    current=current,
                    total=phrase_total,
                    announce=False,
                )

        video = cv2.VideoCapture(str(input_path))
        fps = video.get(cv2.CAP_PROP_FPS)
        scene_total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0:
            video.release()
            raise ValueError("The selected video has an invalid frame rate.")
        frame_time = 1 / fps
        report(
            "scene_indexing",
            "Indexing video scenes.",
            current=0,
            total=scene_total,
        )

        scene_count = 0
        timestamp = 0.0
        while True:
            ret, frame = video.read()
            if not ret:
                break

            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            image = preprocess(image).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                image_features = clip_model.encode_image(image)
                image_features /= image_features.norm(dim=-1, keepdim=True)

            embedding_vector = image_features.cpu().numpy().tolist()[0]
            scene_collection.add(
                ids=[str(scene_count)],
                embeddings=[embedding_vector],
                metadatas=[{"time": timestamp}],
            )

            scene_count += 1
            timestamp += frame_time
            if _should_report_progress(scene_count, scene_total):
                report(
                    "scene_indexing",
                    "Indexing video scenes.",
                    current=scene_count,
                    total=scene_total,
                    announce=False,
                )

        video.release()

        face_match_threshold = 0.55
        history_size = 5
        known_face_encodings = []
        known_face_ids = []
        next_id = 1
        face_history = {}

        def get_best_match(face_encoding):
            if not known_face_encodings:
                return None

            distances = face_recognition.face_distance(
                known_face_encodings,
                face_encoding,
            )
            best_match_idx = distances.argmin()
            if distances[best_match_idx] < face_match_threshold:
                return best_match_idx
            return None

        video = cv2.VideoCapture(str(input_path))
        fps = video.get(cv2.CAP_PROP_FPS)
        actor_total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0:
            video.release()
            raise ValueError("The selected video has an invalid frame rate.")
        frame_time = 1 / fps
        report(
            "actor_indexing",
            "Detecting and clustering actors.",
            current=0,
            total=actor_total,
        )

        faces = []
        actor_frame = 0
        timestamp = 0.0
        while True:
            ret, frame = video.read()
            if not ret:
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(
                rgb_frame,
                face_locations,
                num_jitters=2,
            )

            for face_encoding, face_location in zip(
                face_encodings,
                face_locations,
            ):
                match_idx = get_best_match(face_encoding)
                if match_idx is not None:
                    face_id = known_face_ids[match_idx]
                    if face_id in face_history:
                        face_history[face_id].append(face_encoding)
                        if len(face_history[face_id]) > history_size:
                            face_history[face_id].pop(0)
                        known_face_encodings[match_idx] = np.mean(
                            face_history[face_id],
                            axis=0,
                        )
                    else:
                        face_history[face_id] = [face_encoding]
                else:
                    face_id = str(next_id)
                    next_id += 1
                    known_face_encodings.append(face_encoding)
                    known_face_ids.append(face_id)
                    face_history[face_id] = [face_encoding]

                faces.append(
                    {
                        "time": round(timestamp, 3),
                        "face_encoding": face_encoding,
                        "face_location": face_location,
                        "actor_id": face_id,
                    }
                )

            actor_frame += 1
            timestamp += frame_time
            if _should_report_progress(actor_frame, actor_total):
                report(
                    "actor_indexing",
                    "Detecting and clustering actors.",
                    current=actor_frame,
                    total=actor_total,
                    announce=False,
                )

        video.release()

        buckets = {}
        for face in faces:
            buckets.setdefault(face["actor_id"], []).append(face)

        actor_count = 0
        for actor_id, face_group in buckets.items():
            if len(face_group) <= 3:
                continue

            times_str = ",".join(str(item["time"]) for item in face_group)
            face_str = ",".join(
                str(item["face_location"])
                for item in face_group
            )
            actor_collection.add(
                ids=[actor_id],
                documents=["-"],
                metadatas=[{"time": times_str, "face_location": face_str}],
            )
            actor_count += 1

        summary = {
            "language": detected_language,
            "dialogue_phrases": phrase_total,
            "scene_frames": scene_count,
            "actor_frames": actor_frame,
            "actor_clusters": actor_count,
        }
        write_index_status(
            state="ready",
            stage="complete",
            message="Video indexing completed successfully.",
            video=video_info,
            summary=summary,
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "complete",
                    "message": "Video indexing completed successfully.",
                    "current": 1,
                    "total": 1,
                    "summary": summary,
                }
            )
        print("[bold green]Video Indexing Complete !!![/bold green]")
        return summary
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        write_index_status(
            state="failed",
            stage=current_stage,
            message=f"Indexing failed during {current_stage.replace('_', ' ')}.",
            video=video_info,
            error=error_message,
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "failed",
                    "message": "Video indexing failed.",
                    "current": None,
                    "total": None,
                    "error": error_message,
                }
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

    query = dialogue
    query_embedding = embedder.encode(query, convert_to_tensor=True)

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
    time = metadatas[0][0]["start"]

    print("[green]Dialogue found !!![/green]")
    return time


@app.command()
def scene(scene: str):
    import clip
    import torch

    require_ready_index()
    clip_model, _ = get_clip_model()
    _, scene_collection, _ = get_collections()

    print("[green]Searching scene...[/green]")

    query = scene
    query = clip.tokenize([query]).to(DEVICE)

    with torch.no_grad():
        query_features = clip_model.encode_text(query)
        query_features /= query_features.norm(dim=-1, keepdim=True)

    query_embedding = query_features.cpu().numpy().tolist()[0]

    result = scene_collection.query(
        query_embeddings=[query_embedding],
        include=["metadatas"],
        n_results=1,
    )
    metadatas = result.get("metadatas") or []
    if not metadatas or not metadatas[0]:
        raise IndexNotReadyError(
            "The completed index contains no searchable scene frames."
        )
    time = metadatas[0][0]["time"]

    print("[green]Scene found...[/green]")
    return time


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
    times = [float(t) for t in metadata["time"].split(",")]
    face_locs = [
        literal_eval(loc + ")") if not loc.endswith(")") else literal_eval(loc)
        for loc in metadata["face_location"].split("),")
    ]

    video = cv2.VideoCapture(input_path)
    fps = video.get(cv2.CAP_PROP_FPS)
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*"avc1"), fps, (width, height))

    frame_targets = {round(t * fps): loc for t, loc in zip(times, face_locs)}
    frame_idx = 0

    while True:
        ret, frame = video.read()
        if not ret:
            break

        if frame_idx in frame_targets:
            top, right, bottom, left = frame_targets[frame_idx]
            color = (0, 255, 0)
            thickness = max(2, int(height / 200))
            font_scale = max(0.5, height / 1000)

            cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)
            cv2.putText(frame, f"Actor {id}", (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)

        writer.write(frame)
        frame_idx += 1

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
