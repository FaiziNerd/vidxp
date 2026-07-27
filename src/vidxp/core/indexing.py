"""Public indexing entry points.

Implementation details live in the modality-specific modules. These wrappers
remain for callers that index one visual modality at a time.
"""

from __future__ import annotations

from typing import Any

from vidxp.core.contracts import VideoSource
from vidxp.core.indexing_dialogue import (
    DialoguePhrase,
    build_dialogue_phrases,
    index_dialogue,
    transcribe_video,
)
from vidxp.core.indexing_visual import VisualIndexResult, index_visuals


def index_scenes(source: VideoSource, **options: Any) -> dict[str, Any]:
    return dict(index_visuals(source, modalities=("scene",), **options).summary)


def index_actors(source: VideoSource, **options: Any) -> dict[str, Any]:
    return dict(index_visuals(source, modalities=("actor",), **options).summary)


__all__ = [
    "DialoguePhrase",
    "VisualIndexResult",
    "build_dialogue_phrases",
    "index_actors",
    "index_dialogue",
    "index_scenes",
    "index_visuals",
    "transcribe_video",
]
