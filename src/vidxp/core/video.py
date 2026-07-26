from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Iterator

from vidxp.core.contracts import CancellationToken


@dataclass(frozen=True)
class VideoInfo:
    fps: float
    frame_count: int
    duration: float
    width: int
    height: int


@dataclass
class FrameStreamStats:
    frames_advanced: int = 0
    frames_materialized: int = 0


@dataclass(frozen=True)
class FrameSample:
    frame_index: int
    timestamp: float
    frame: object


def ffmpeg_binary() -> str:
    from moviepy.config import get_setting

    configured = get_setting("FFMPEG_BINARY")
    configured_path = Path(str(configured))
    resolved = (
        str(configured_path.resolve())
        if configured_path.is_file()
        else which(str(configured))
    )
    if not resolved:
        raise RuntimeError(f"FFmpeg executable was not found: {configured}")
    return resolved


def probe_video(path: str | Path) -> VideoInfo:
    import cv2

    video = cv2.VideoCapture(str(path))
    try:
        fps = float(video.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            raise ValueError("The selected video has an invalid frame rate.")
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        return VideoInfo(
            fps=fps,
            frame_count=frame_count,
            duration=frame_count / fps,
            width=int(video.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
    finally:
        video.release()


def iter_frame_batches(
    path: str | Path,
    *,
    frame_stride: int,
    batch_size: int,
    cancellation: CancellationToken,
    stats: FrameStreamStats | None = None,
) -> Iterator[list[FrameSample]]:
    import cv2

    if frame_stride <= 0:
        raise ValueError("frame_stride must be greater than zero.")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    video = cv2.VideoCapture(str(path))
    fps = float(video.get(cv2.CAP_PROP_FPS))
    if fps <= 0:
        video.release()
        raise ValueError("The selected video has an invalid frame rate.")

    stream_stats = stats or FrameStreamStats()
    batch: list[FrameSample] = []
    frame_index = 0
    try:
        while True:
            sampled = frame_index % frame_stride == 0
            if sampled:
                retrieved, frame = video.read()
            else:
                retrieved = video.grab()
                frame = None
            if not retrieved:
                break
            stream_stats.frames_advanced += 1
            if sampled:
                stream_stats.frames_materialized += 1
                batch.append(
                    FrameSample(
                        frame_index=frame_index,
                        timestamp=frame_index / fps,
                        frame=frame,
                    )
                )
                if len(batch) == batch_size:
                    cancellation.raise_if_cancelled()
                    yield batch
                    batch = []
            frame_index += 1
        if batch:
            cancellation.raise_if_cancelled()
            yield batch
    finally:
        video.release()


def extract_audio(input_path: str | Path, output_path: str | Path) -> Path:
    from moviepy.editor import VideoFileClip

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with VideoFileClip(str(input_path)) as source_video:
        if source_video.audio is None:
            raise ValueError("The selected video does not contain an audio track.")
        source_video.audio.write_audiofile(str(destination), logger=None)
    return destination


def render_actor_video(
    input_path: str | Path,
    output_path: str | Path,
    cluster_id: str,
    detections: list[dict],
) -> None:
    import cv2

    source = cv2.VideoCapture(str(input_path))
    fps = float(source.get(cv2.CAP_PROP_FPS))
    width = int(source.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(source.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"avc1"),
        fps,
        (width, height),
    )
    frame_targets = {
        int(item["frame_index"]): tuple(item["bbox"])
        for item in detections
    }

    try:
        frame_index = 0
        while True:
            retrieved, frame = source.read()
            if not retrieved:
                break
            if frame_index in frame_targets:
                top, right, bottom, left = frame_targets[frame_index]
                color = (0, 255, 0)
                thickness = max(2, int(height / 200))
                font_scale = max(0.5, height / 1000)
                cv2.rectangle(
                    frame,
                    (left, top),
                    (right, bottom),
                    color,
                    thickness,
                )
                cv2.putText(
                    frame,
                    f"Actor {cluster_id}",
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale,
                    color,
                    thickness,
                )
            writer.write(frame)
            frame_index += 1
    finally:
        source.release()
        writer.release()
