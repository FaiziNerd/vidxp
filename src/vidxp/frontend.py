import sys
from pathlib import Path

import streamlit as st

from vidxp.main import actor, dialogue, scene, videoindex


def run():
    st.title("VidXP (Video eXPlain) - Video Indexing Engine")
    uploaded_video = st.file_uploader("Upload a video", type=["mp4", "mov", "avi"])

    if uploaded_video:
        st.video(uploaded_video)

    index_button = st.button("Index Video")
    option = st.selectbox("What do you want to search ?", ["scene", "dialogue", "actor"])

    col1, col2 = st.columns([7, 1])

    with col1:
        query = st.text_input(
            "Enter your query:",
            label_visibility="collapsed",
            placeholder="Enter your query:",
        )

    with col2:
        search_button = st.button("Search")

    if index_button:
        if uploaded_video is None:
            st.error("Upload a video before indexing.")
        else:
            with st.spinner("Indexing video"):
                with open("video.mp4", "wb") as f:
                    f.write(uploaded_video.read())
                videoindex("video.mp4")

    if search_button:
        if option == "dialogue":
            time = float(dialogue(query))
            st.video(uploaded_video, start_time=time)
        elif option == "scene":
            time = float(scene(query))
            st.video(uploaded_video, start_time=time)
        elif option == "actor":
            actor(query, "video.mp4")
            st.video("./output.mp4", format="video/mp4", start_time=0)


def main():
    from streamlit.web import cli as streamlit_cli

    sys.argv = ["streamlit", "run", str(Path(__file__).resolve()), *sys.argv[1:]]
    raise SystemExit(streamlit_cli.main())


if __name__ == "__main__":
    run()
