from multiprocessing import get_context
from multiprocessing.process import BaseProcess
from threading import Lock

from vidxp.index_state import IndexingInProgressError
from vidxp.main import index_video, indexing_in_progress as in_process_indexing

_process: BaseProcess | None = None
_start_lock = Lock()


def indexing_in_progress() -> bool:
    return (_process is not None and _process.is_alive()) or in_process_indexing()


def start_indexing(path: str, source_name: str) -> None:
    global _process

    with _start_lock:
        if indexing_in_progress():
            raise IndexingInProgressError("Another video is already being indexed.")

        _process = get_context("spawn").Process(
            target=index_video,
            args=(path, None, source_name),
            name="vidxp-indexer",
            daemon=True,
        )
        _process.start()
