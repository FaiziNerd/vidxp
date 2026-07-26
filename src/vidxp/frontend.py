import hashlib
import sys
from pathlib import Path

import streamlit as st

from vidxp.index_state import (
    IndexingInProgressError,
    IndexNotReadyError,
    read_index_status,
)
from vidxp.main import (
    actor,
    dialogue,
    index_video,
    indexing_in_progress,
    scene,
)


SAVED_VIDEO_PATH = Path("video.mp4")


def _uploaded_video_hash(uploaded_video) -> str | None:
    if uploaded_video is None:
        return None
    return hashlib.sha256(uploaded_video.getvalue()).hexdigest()


def _status_matches_video(status, uploaded_video) -> bool:
    if not status or status.get("state") != "ready":
        return False
    if uploaded_video is None:
        return SAVED_VIDEO_PATH.is_file()
    return (
        status.get("video", {}).get("sha256")
        == _uploaded_video_hash(uploaded_video)
    )


def _render_summary(summary):
    if not summary:
        return
    columns = st.columns(4)
    columns[0].metric("Language", summary.get("language", "—"))
    columns[1].metric(
        "Dialogue phrases",
        summary.get("dialogue_phrases", 0),
    )
    columns[2].metric("Scene frames", summary.get("scene_frames", 0))
    columns[3].metric("Actor clusters", summary.get("actor_clusters", 0))


def _render_saved_status():
    status = read_index_status()
    active = indexing_in_progress()

    if active:
        message = "Indexing is running."
        if status and status.get("state") == "indexing":
            message = status.get("message", message)
        status_container = st.status(
            message,
            expanded=True,
            state="running",
        )
        if status:
            current = status.get("current")
            total = status.get("total")
            if current is not None and total:
                status_container.progress(
                    min(current / total, 1.0),
                    text=f"{current:,} of {total:,}",
                )
            status_container.caption(
                f"Stage: {status.get('stage', 'initializing').replace('_', ' ')}"
            )
        status_container.caption(
            "The saved video and index remain on disk if this page is reloaded."
        )
        return

    if not status:
        return

    state = status.get("state")
    if state == "ready":
        st.success(status.get("message", "The video index is ready."))
        _render_summary(status.get("summary"))
    elif state == "failed":
        st.error(status.get("message", "Video indexing failed."))
        if status.get("error"):
            st.code(status["error"])
    elif state == "indexing":
        st.warning(
            "The previous indexing run did not reach completion. "
            "Restart indexing before searching."
        )
        st.caption(
            f"Last recorded stage: {status.get('stage', 'unknown').replace('_', ' ')}"
        )


def run():
    st.set_page_config(
        page_title="VidXP",
        page_icon="🎬",
        layout="wide",
    )
    st.title("VidXP")
    st.caption("Index and search video by dialogue, scene, and actor.")

    active = indexing_in_progress()
    status = read_index_status()

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

    poll_interval = "1s" if active else None

    @st.fragment(run_every=poll_interval)
    def index_status():
        _render_saved_status()
        if active and not indexing_in_progress():
            st.rerun()

    index_status()

    st.subheader("2. Build index")
    st.info(
        "Installing VidXP installs the application and Python dependencies, "
        "not its runtime model weights. The first indexing run downloads any "
        "missing dialogue, scene, transcription, and language-alignment models. "
        "Keep the terminal and internet connection open until the index is ready."
    )

    available_video = uploaded_video is not None or SAVED_VIDEO_PATH.is_file()
    index_button = st.button(
        "Index video",
        type="primary",
        disabled=active or not available_video,
        help=(
            "Another indexing run is active."
            if active
            else "Build or replace the searchable index for this video."
        ),
    )

    ready_for_search = (
        not active
        and not index_button
        and _status_matches_video(status, uploaded_video)
    )

    st.subheader("3. Search")
    if uploaded_video is not None and not ready_for_search:
        st.caption("Index this uploaded video before searching it.")
    elif not ready_for_search:
        st.caption("Search becomes available after indexing completes.")

    option = st.selectbox(
        "Search type",
        ["scene", "dialogue", "actor"],
        disabled=not ready_for_search,
    )
    query_label = "Actor cluster ID" if option == "actor" else "Search query"
    query = st.text_input(
        query_label,
        placeholder=(
            "For example: Chef makes pizza and cuts it up."
            if option != "actor"
            else "For example: 1"
        ),
        disabled=not ready_for_search,
    )
    search_button = st.button(
        "Search",
        disabled=not ready_for_search or not query.strip(),
    )

    if index_button:
        if uploaded_video is not None:
            SAVED_VIDEO_PATH.write_bytes(uploaded_video.getvalue())
            source_name = uploaded_video.name
        else:
            source_name = (
                status.get("video", {}).get(
                    "source_name",
                    SAVED_VIDEO_PATH.name,
                )
                if status
                else SAVED_VIDEO_PATH.name
            )

        task_status = st.status(
            "Preparing indexing...",
            expanded=True,
            state="running",
        )
        progress_placeholder = task_status.empty()
        detail_placeholder = task_status.empty()

        def update_progress(event):
            task_status.update(
                label=event["message"],
                state=(
                    "error"
                    if event["stage"] == "failed"
                    else "running"
                ),
            )
            current = event.get("current")
            total = event.get("total")
            if current is not None and total:
                progress_placeholder.progress(
                    min(current / total, 1.0),
                    text=f"{current:,} of {total:,}",
                )
            else:
                progress_placeholder.empty()
            detail_placeholder.caption(
                f"Stage: {event['stage'].replace('_', ' ')}"
            )

        try:
            summary = index_video(
                str(SAVED_VIDEO_PATH),
                progress_callback=update_progress,
                source_name=source_name,
            )
            progress_placeholder.progress(
                1.0,
                text="Indexing complete",
            )
            task_status.update(
                label="Video indexing completed successfully.",
                state="complete",
                expanded=False,
            )
            _render_summary(summary)
            st.rerun()
        except IndexingInProgressError as exc:
            task_status.update(
                label=str(exc),
                state="error",
            )
        except Exception as exc:
            task_status.update(
                label="Video indexing failed.",
                state="error",
            )
            st.error(f"{type(exc).__name__}: {exc}")

    if search_button:
        try:
            if option == "dialogue":
                timestamp = float(dialogue(query))
                st.success(f"Best dialogue match: {timestamp:.3f} seconds")
                st.video(str(SAVED_VIDEO_PATH), start_time=timestamp)
            elif option == "scene":
                timestamp = float(scene(query))
                st.success(f"Best scene match: {timestamp:.3f} seconds")
                st.video(str(SAVED_VIDEO_PATH), start_time=timestamp)
            else:
                actor(query, str(SAVED_VIDEO_PATH))
                st.success(f"Generated actor result for cluster {query}.")
                st.video("output.mp4", format="video/mp4", start_time=0)
        except IndexNotReadyError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"{type(exc).__name__}: {exc}")


def main():
    from streamlit.web import cli as streamlit_cli

    sys.argv = [
        "streamlit",
        "run",
        str(Path(__file__).resolve()),
        *sys.argv[1:],
    ]
    raise SystemExit(streamlit_cli.main())


if __name__ == "__main__":
    run()
