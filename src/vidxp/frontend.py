import hashlib
import sys
from pathlib import Path

import streamlit as st

from vidxp.index_state import (
    IndexingInProgressError,
    IndexNotReadyError,
    read_index_status,
)
from vidxp.main import actor, dialogue, index_video, indexing_in_progress, scene

SAVED_VIDEO_PATH = Path("video.mp4")


def _video_hash(uploaded_video) -> str | None:
    if uploaded_video is None:
        return None
    return hashlib.sha256(uploaded_video.getvalue()).hexdigest()


def _is_search_ready(status, uploaded_video) -> bool:
    if not status or status.get("state") != "ready":
        return False
    if uploaded_video is None:
        return SAVED_VIDEO_PATH.is_file()
    return status.get("video", {}).get("sha256") == _video_hash(uploaded_video)


def _render_summary(summary):
    if not summary:
        return
    columns = st.columns(4)
    for column, label, key, fallback in zip(
        columns,
        ("Language", "Dialogue phrases", "Scene frames", "Actor clusters"),
        ("language", "dialogue_phrases", "scene_frames", "actor_clusters"),
        ("—", 0, 0, 0),
    ):
        column.metric(label, summary.get(key, fallback))


def _update_progress(container, progress, detail, event):
    state = {
        "ready": "complete",
        "failed": "error",
    }.get(event.get("state"), "running")
    container.update(label=event["message"], state=state)

    current, total = event.get("current"), event.get("total")
    if current is not None and total:
        progress.progress(
            min(current / total, 1.0),
            text=f"{current:,} of {total:,}",
        )
    else:
        progress.empty()
    detail.caption(f"Stage: {event['stage'].replace('_', ' ')}")


def _render_index_status(status, active):
    if active:
        event = status or {
            "state": "indexing",
            "stage": "initializing",
            "message": "Indexing is running.",
        }
        container = st.status(event["message"], expanded=True, state="running")
        _update_progress(container, container.empty(), container.empty(), event)
        container.caption(
            "The saved video and index remain on disk if this page is reloaded."
        )
    elif not status:
        return
    elif status["state"] == "ready":
        st.success(status.get("message", "The video index is ready."))
        _render_summary(status.get("summary"))
    elif status["state"] == "failed":
        st.error(status.get("message", "Video indexing failed."))
        if status.get("error"):
            st.code(status["error"])
    elif status["state"] == "indexing":
        st.warning(
            "The previous indexing run did not finish. Restart it before searching."
        )
        st.caption(
            f"Last recorded stage: {status.get('stage', 'unknown').replace('_', ' ')}"
        )


def _run_indexing(uploaded_video, status):
    task = st.status("Preparing indexing...", expanded=True, state="running")
    progress, detail = task.empty(), task.empty()

    def update(event):
        _update_progress(task, progress, detail, event)

    try:
        if uploaded_video is not None:
            SAVED_VIDEO_PATH.write_bytes(uploaded_video.getvalue())
            source_name = uploaded_video.name
        else:
            source_name = (
                status.get("video", {}).get("source_name", SAVED_VIDEO_PATH.name)
                if status
                else SAVED_VIDEO_PATH.name
            )
        index_video(
            str(SAVED_VIDEO_PATH),
            progress_callback=update,
            source_name=source_name,
        )
    except IndexingInProgressError as exc:
        task.update(label=str(exc), state="error")
    except Exception as exc:
        st.error(f"{type(exc).__name__}: {exc}")
    else:
        st.rerun()


def _run_search(search_type, query):
    try:
        if search_type == "actor":
            actor(query, str(SAVED_VIDEO_PATH))
            st.success(f"Generated actor result for cluster {query}.")
            st.video("output.mp4", format="video/mp4")
            return

        finder = dialogue if search_type == "dialogue" else scene
        timestamp = float(finder(query))
        st.success(f"Best {search_type} match: {timestamp:.3f} seconds")
        st.video(str(SAVED_VIDEO_PATH), start_time=timestamp)
    except IndexNotReadyError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"{type(exc).__name__}: {exc}")


def _select_video(active):
    st.subheader("1. Select video")
    uploaded_video = st.file_uploader(
        "Upload an MP4, MOV, or AVI video",
        type=["mp4", "mov", "avi"],
        disabled=active,
        key="video_upload",
    )
    if uploaded_video is not None:
        st.video(uploaded_video)
    elif SAVED_VIDEO_PATH.is_file():
        st.caption("Using the video saved by the current or previous indexing run.")
        st.video(str(SAVED_VIDEO_PATH))
    return uploaded_video


def _search_controls(ready, uploaded_video):
    st.subheader("3. Search")
    if not ready:
        message = (
            "Index this uploaded video before searching it."
            if uploaded_video is not None
            else "Search becomes available after indexing completes."
        )
        st.caption(message)

    search_type = st.selectbox(
        "Search type",
        ["scene", "dialogue", "actor"],
        disabled=not ready,
    )
    query = st.text_input(
        "Actor cluster ID" if search_type == "actor" else "Search query",
        placeholder=(
            "For example: 1"
            if search_type == "actor"
            else "For example: Chef makes pizza and cuts it up."
        ),
        disabled=not ready,
    )
    clicked = st.button("Search", disabled=not ready or not query.strip())
    return clicked, search_type, query


def run():
    st.set_page_config(page_title="VidXP", page_icon="🎬", layout="wide")
    st.title("VidXP")
    st.caption("Index and search video by dialogue, scene, and actor.")

    active = indexing_in_progress()
    status = read_index_status()
    uploaded_video = _select_video(active)

    @st.fragment(run_every="1s" if active else None)
    def poll_index_status():
        latest_active = indexing_in_progress()
        _render_index_status(read_index_status(), latest_active)
        if active and not latest_active:
            st.rerun()

    poll_index_status()

    st.subheader("2. Build index")
    st.info(
        "Installing VidXP does not download its runtime model weights. The first "
        "indexing run downloads any missing models. Keep the terminal and internet "
        "connection open until the index is ready."
    )
    index_clicked = st.button(
        "Index video",
        type="primary",
        disabled=active
        or (uploaded_video is None and not SAVED_VIDEO_PATH.is_file()),
        help=(
            "Another indexing run is active."
            if active
            else "Build or replace the searchable index for this video."
        ),
    )

    ready = (
        not active
        and not index_clicked
        and _is_search_ready(status, uploaded_video)
    )
    search_clicked, search_type, query = _search_controls(
        ready,
        uploaded_video,
    )

    if index_clicked:
        _run_indexing(uploaded_video, status)
    if search_clicked:
        _run_search(search_type, query)


def main():
    from streamlit.web import cli as streamlit_cli

    sys.argv = ["streamlit", "run", str(Path(__file__).resolve()), *sys.argv[1:]]
    raise SystemExit(streamlit_cli.main())


if __name__ == "__main__":
    run()
