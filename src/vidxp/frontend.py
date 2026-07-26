import hashlib
import sys
from pathlib import Path

import streamlit as st

from vidxp.index_state import (
    IndexNotReadyError,
    read_index_status,
)
from vidxp.main import actor, dialogue, index_video, indexing_in_progress, scene

SAVED_VIDEO_PATH = Path("video.mp4")
INDEX_REQUESTED_KEY = "_vidxp_index_requested"
INDEX_ERROR_KEY = "_vidxp_index_error"


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
    st.caption(
        " · ".join(
            (
                f"Language: {summary.get('language', '—')}",
                f"Dialogue phrases: {summary.get('dialogue_phrases', 0):,}",
                f"Scene frames: {summary.get('scene_frames', 0):,}",
                f"Actor clusters: {summary.get('actor_clusters', 0):,}",
            )
        )
    )


def _update_progress(container, progress, event):
    state = {
        "ready": "complete",
        "failed": "error",
    }.get(event.get("state"), "running")
    container.update(label=event["message"], expanded=False, state=state)

    current, total = event.get("current"), event.get("total")
    if current is not None and total:
        progress.progress(
            min(current / total, 1.0),
            text=f"{current:,} of {total:,}",
        )
    else:
        progress.empty()


def _render_index_status(status, active, uploaded_video, request_error=None):
    if request_error:
        st.error(request_error)
        return

    if active:
        event = status or {
            "state": "indexing",
            "stage": "initializing",
            "message": "Indexing is running.",
        }
        container = st.status(
            event["message"],
            expanded=False,
            state="running",
            type="compact",
        )
        _update_progress(container, st.empty(), event)
    elif not status:
        st.caption("First indexing may download missing runtime model weights.")
    elif status["state"] == "ready":
        if _is_search_ready(status, uploaded_video):
            st.success(status.get("message", "The video index is ready."))
            _render_summary(status.get("summary"))
        else:
            st.info("The selected video has not been indexed yet.")
    elif status["state"] == "failed":
        st.error(status.get("message", "Video indexing failed."))
        if status.get("error"):
            with st.expander("Error details"):
                st.code(status["error"])
    elif status["state"] == "indexing":
        st.warning(
            "The previous run stopped while "
            f"{status.get('stage', 'indexing').replace('_', ' ')}. "
            "Restart indexing before searching."
        )


def _request_indexing():
    st.session_state[INDEX_REQUESTED_KEY] = True
    st.session_state.pop(INDEX_ERROR_KEY, None)


def _run_indexing(uploaded_video, status, task, progress):
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
            progress_callback=lambda event: _update_progress(task, progress, event),
            source_name=source_name,
        )
    except Exception as exc:
        st.session_state[INDEX_ERROR_KEY] = f"{type(exc).__name__}: {exc}"
    else:
        st.session_state.pop(INDEX_ERROR_KEY, None)
    finally:
        st.session_state[INDEX_REQUESTED_KEY] = False
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


def _select_video(busy):
    st.subheader("Video")
    has_session_upload = st.session_state.get("video_upload") is not None
    if busy and not has_session_upload and SAVED_VIDEO_PATH.is_file():
        uploaded_video = None
        st.caption("Indexing the saved video.")
    else:
        uploaded_video = st.file_uploader(
            "Upload an MP4, MOV, or AVI video",
            type=["mp4", "mov", "avi"],
            disabled=busy,
            key="video_upload",
        )

    if uploaded_video is not None:
        st.video(uploaded_video, width=560)
    elif SAVED_VIDEO_PATH.is_file():
        if not busy:
            st.caption("Using the saved video.")
        st.video(str(SAVED_VIDEO_PATH), width=560)
    return uploaded_video


def _search_controls(ready, uploaded_video):
    st.subheader("Search")
    if not ready:
        message = (
            "Index this uploaded video before searching it."
            if uploaded_video is not None
            else "Search becomes available after indexing completes."
        )
        st.caption(message)

    type_column, query_column = st.columns(
        [0.35, 0.65],
        gap="small",
        vertical_alignment="bottom",
    )
    with type_column:
        search_type = st.selectbox(
            "Search type",
            ["scene", "dialogue", "actor"],
            disabled=not ready,
        )
    with query_column:
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
    requested = st.session_state.get(INDEX_REQUESTED_KEY, False)
    busy = active or requested
    status = read_index_status()
    video_column, workflow_column = st.columns(
        [0.95, 1.05],
        gap="large",
        vertical_alignment="top",
    )

    with video_column:
        uploaded_video = _select_video(busy)

    with workflow_column:
        st.subheader("Build index")
        st.button(
            "Index video",
            type="primary",
            disabled=busy
            or (uploaded_video is None and not SAVED_VIDEO_PATH.is_file()),
            help=(
                "Indexing is already running."
                if busy
                else "Build or replace the index. First use may download model weights."
            ),
            on_click=_request_indexing,
        )

        if requested:
            task = st.status(
                "Preparing indexing...",
                expanded=False,
                state="running",
                type="compact",
            )
            progress = st.empty()
        elif active:

            @st.fragment(run_every="1s")
            def poll_index_status():
                latest_active = indexing_in_progress()
                _render_index_status(
                    read_index_status(),
                    latest_active,
                    uploaded_video,
                    st.session_state.get(INDEX_ERROR_KEY),
                )
                if not latest_active:
                    st.rerun()

            poll_index_status()
        else:
            _render_index_status(
                status,
                False,
                uploaded_video,
                st.session_state.get(INDEX_ERROR_KEY),
            )

        ready = not busy and _is_search_ready(status, uploaded_video)
        search_clicked, search_type, query = _search_controls(
            ready,
            uploaded_video,
        )

    if requested:
        _run_indexing(uploaded_video, status, task, progress)
    if search_clicked:
        _run_search(search_type, query)


def main():
    from streamlit.web import cli as streamlit_cli

    sys.argv = ["streamlit", "run", str(Path(__file__).resolve()), *sys.argv[1:]]
    raise SystemExit(streamlit_cli.main())


if __name__ == "__main__":
    run()
