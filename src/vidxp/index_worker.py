from multiprocessing import get_context
from multiprocessing.process import BaseProcess
from threading import Lock

from vidxp.core.contracts import CancellationToken
from vidxp.core.runner import (
    index_video,
    indexing_in_progress as in_process_indexing,
)
from vidxp.index_state import IndexingInProgressError

_process: BaseProcess | None = None
_cancel_event = None
_start_lock = Lock()


def _run_indexing(path: str, source_name: str, cancel_event) -> None:
    index_video(
        path,
        source_name=source_name,
        cancellation=CancellationToken(cancel_event),
    )


def indexing_in_progress() -> bool:
    return (_process is not None and _process.is_alive()) or in_process_indexing()


def start_indexing(path: str, source_name: str) -> None:
    global _cancel_event, _process

    with _start_lock:
        if indexing_in_progress():
            raise IndexingInProgressError("Another video is already being indexed.")

        context = get_context("spawn")
        _cancel_event = context.Event()
        _process = context.Process(
            target=_run_indexing,
            args=(path, source_name, _cancel_event),
            name="vidxp-indexer",
            daemon=True,
        )
        _process.start()


def cancel_indexing() -> bool:
    if _process is None or not _process.is_alive() or _cancel_event is None:
        return False
    _cancel_event.set()
    return True
