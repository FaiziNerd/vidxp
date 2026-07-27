from __future__ import annotations

from typing import Any, Callable


ProgressCallback = Callable[[dict[str, Any]], None]


def report_progress(
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
