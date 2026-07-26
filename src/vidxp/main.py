"""Compatibility imports for the pre-refactor ``vidxp.main`` surface.

New code should import CLI commands from :mod:`vidxp.cli` and programmatic
indexing/search APIs from :mod:`vidxp.core`.
"""

from vidxp.cli import (
    actor,
    app,
    dialogue,
    doctor,
    main,
    prepare,
    scene,
    videoindex,
)
from vidxp.core.runner import index_video, indexing_in_progress, run_index
from vidxp.core.search import search, search_dialogue, search_scene

__all__ = [
    "actor",
    "app",
    "dialogue",
    "doctor",
    "index_video",
    "indexing_in_progress",
    "main",
    "prepare",
    "run_index",
    "scene",
    "search",
    "search_dialogue",
    "search_scene",
    "videoindex",
]


if __name__ == "__main__":
    main()
