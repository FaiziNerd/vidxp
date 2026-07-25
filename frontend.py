import streamlit as st
from main import videoindex, dialogue, scene, actor

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
        placeholder="Enter your query:"
    )

with col2:
    search_button = st.button("Search")

if index_button:
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
