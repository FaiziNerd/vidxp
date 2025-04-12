
import streamlit as st
import os
import tempfile
import time # For minor delays or timestamps

# --- Assuming actordb package is installed and main.py is accessible ---
# --- This section attempts to import the original functions      ---
ACTORDB_FUNCTIONS_LOADED = False
try:
    from actordb.main import videoindex, dialogue, scene
    ACTORDB_FUNCTIONS_LOADED = True
except ImportError as e:
    st.error(
        f"*Error:* Could not import functions from actordb.main. "
        f"Ensure the actordb package is installed correctly (e.g., pip install -e . "
        f"in the parent directory) and actordb/main.py exists. Details: {e}"
    )
    st.stop() # Stop if backend functions can't be loaded
# --------------------------------------------------------------------

# --- Streamlit Page Config ---
st.set_page_config(
    layout="wide",
    page_title="ActorDB Pro Search",
    page_icon="🎬" # Add a page icon
)

# --- Session State Initialization ---
# Use more descriptive keys and initialize all expected states
if 'video_temp_path' not in st.session_state: st.session_state.video_temp_path = None
if 'video_buffer' not in st.session_state: st.session_state.video_buffer = None
if 'video_filename' not in st.session_state: st.session_state.video_filename = None
if 'video_start_time' not in st.session_state: st.session_state.video_start_time = 0
# Add state for index check/status - Assume not indexed initially
if 'video_is_indexed_checked' not in st.session_state: st.session_state.video_is_indexed_checked = False
if 'video_index_status_msg' not in st.session_state: st.session_state.video_index_status_msg = "Status Unknown"
if 'last_uploaded_id' not in st.session_state: st.session_state.last_uploaded_id = None
if 'search_type_selected' not in st.session_state: st.session_state.search_type_selected = "Dialogue" # Default


# --- UI Styling (Optional - Simple CSS Injection) ---
# st.markdown("""
# <style>
#     /* Add minor styling adjustments if desired */
#     .stButton>button {
#         border-radius: 5px;
#     }
#     .stSpinner > div {
#         text-align: center;
#     }
# </style>
# """, unsafe_allow_html=True)


# --- Helper Function (Placeholder - Actual check is difficult) ---
# NOTE: We cannot reliably check if indexing is actually done by the
# external videoindex function without modifying it or inspecting the DB.
# This function is a placeholder for the UI logic.
def check_index_status_placeholder(filename):
    # In a real scenario calling external functions, this is hard.
    # We'll just return the last known state or assume unknown/false.
    if st.session_state.video_is_indexed_checked:
        return st.session_state.video_index_status_msg
    else:
        # Maybe try a quick DB check if possible, otherwise assume not checked.
        # For this example, we'll just reflect the lack of check.
        return "Status Unknown (Index video if needed)"


# ==============================================================================
#                              Streamlit UI Layout
# ==============================================================================

# --- Header ---
col_h1, col_h2 = st.columns([1, 6])
with col_h1:
    st.image("https://img.icons8.com/fluency/96/film-reel.png", width=70)
with col_h2:
    st.title("ActorDB Pro Search")
    st.caption("Visually search your videos using AI-powered dialogue and scene understanding.")

# --- Sidebar ---
with st.sidebar:
    st.header("🎬 Video Input")
    uploaded_file = st.file_uploader(
        "Upload Video File",
        type=["mp4", "avi", "mov", "mkv"],
        key="uploader_sidebar",
        help="Select the video you want to index and search."
    )

    # Process New Upload
    if uploaded_file is not None:
        current_file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        if current_file_id != st.session_state.last_uploaded_id:
            # Reset state before processing new file
            st.session_state.video_temp_path = None; st.session_state.video_buffer = None
            st.session_state.video_filename = None; st.session_state.video_start_time = 0
            st.session_state.video_is_indexed_checked = False; st.session_state.video_index_status_msg = "Status Unknown"
            st.session_state.last_uploaded_id = current_file_id # Mark as being processed

            st.info(f"Loading '{uploaded_file.name}'...")
            try:
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    st.session_state.video_temp_path = tmp.name
                st.session_state.video_buffer = uploaded_file # Keep buffer for display
                st.session_state.video_filename = uploaded_file.name
                # We cannot reliably check index status without calling DB or modifying backend
                st.session_state.video_is_indexed_checked = False # Assume unchecked on new load
                st.session_state.video_index_status_msg = "Index Status Unchecked"
                st.success(f"'{uploaded_file.name}' loaded.")
                st.rerun() # Update UI
            except Exception as e:
                st.error(f"File handling error: {e}")
                st.session_state.last_uploaded_id = None # Reset to allow re-attempt


    # Display Controls if Video Loaded
    if st.session_state.video_temp_path:
        st.markdown("---")
        st.subheader("Current Video")
        st.info(f"*File:* {st.session_state.video_filename}")
        st.info(f"*Index Status:* {st.session_state.video_index_status_msg}")

        st.subheader("Actions")
        # Index Button
        if st.button("📊 Index This Video", key="indexer_sidebar", help="Processes the video for searching (can take time). Check console for detailed progress."):
            with st.spinner("⏳ Indexing video (check console)..."):
                indexing_start_time = time.time()
                try:
                    # --- Call original videoindex function ---
                    videoindex(st.session_state.video_temp_path)
                    # --- Function finished ---
                    indexing_duration = time.time() - indexing_start_time
                    # Assume indexing worked if no exception, but we can't be sure
                    st.session_state.video_is_indexed_checked = True
                    st.session_state.video_index_status_msg = "Indexing Completed (Assumed)"
                    st.success(f"Indexing command finished in ~{indexing_duration:.0f}s (Check console).")
                    time.sleep(1) # Brief pause
                    st.rerun()
                except Exception as e:
                    st.error(f"Indexing command failed: {e}")

        # Unload Button
        if st.button("🗑 Unload Video", key="unloader_sidebar"):
             if st.session_state.video_temp_path and os.path.exists(st.session_state.video_temp_path):
                  try: os.remove(st.session_state.video_temp_path)
                  except OSError: pass
             # Reset state
             st.session_state.video_temp_path = None; st.session_state.video_buffer = None; st.session_state.video_filename = None
             st.session_state.video_start_time = 0; st.session_state.video_is_indexed_checked = False
             st.session_state.video_index_status_msg = "Status Unknown"; st.session_state.last_uploaded_id = None
             st.info("Video unloaded."); st.rerun()

    else:
        st.info("Upload a video file to activate controls.")


# --- Main Area ---
if st.session_state.video_buffer:
    # --- Video Player ---
    st.subheader("▶ Video Player")
    st.video(st.session_state.video_buffer, start_time=st.session_state.video_start_time)
    st.divider()

    # --- Search Area ---
    st.subheader("🔍 Search Within Video")
    # Let user search even if index status is unknown/unchecked, function might still work
    search_col1, search_col2 = st.columns([2,3]) # Give more space to input

    with search_col1:
        search_type = st.selectbox(
            "Select Search Type:",
            ("Dialogue", "Scene"),
            key='search_type_main',
            label_visibility="collapsed" # Hide label if header is enough
        )
        st.session_state.search_type_selected = search_type

    with search_col2:
        query = None
        search_func = None
        button_label = None
        placeholder_text = ""

        if st.session_state.search_type_selected == "Dialogue":
            placeholder_text = "Enter spoken words or phrases..."
            query = st.text_input("Search Query", placeholder=placeholder_text, key="dialogue_query_main", label_visibility="collapsed")
            search_func = dialogue
            button_label = "🗣 Find Dialogue"
        elif st.session_state.search_type_selected == "Scene":
            placeholder_text = "Describe the scene visually..."
            query = st.text_input("Search Query", placeholder=placeholder_text, key="scene_query_main", label_visibility="collapsed")
            search_func = scene
            button_label = "🖼 Find Scene"

    # Search Button (aligned below or beside depending on layout)
    if button_label and st.button(button_label, key="search_button_main", type="primary", use_container_width=True):
        if query and search_func:
            with st.spinner(f"Searching {st.session_state.search_type_selected.lower()}..."):
                search_start_time = time.time()
                try:
                    # --- Call original dialogue or scene function ---
                    # We try to capture the return value if adapted, otherwise rely on console
                    returned_time = search_func(st.session_state.video_temp_path, query)
                    # --- Function finished ---
                    search_duration = time.time() - search_start_time

                    if returned_time is not None:
                         st.session_state.video_start_time = int(returned_time) # Update player start time
                         st.success(f"{st.session_state.search_type_selected} found near {returned_time:.2f}s. Player updated. (~{search_duration:.1f}s search)")
                         st.rerun()
                    else:
                         # This happens if the function explicitly returns None or fails silently
                         st.warning(f"No matching {st.session_state.search_type_selected.lower()} found by the search function.")

                except Exception as e:
                    st.error(f"Search command failed: {e}")
        else:
            st.warning("Please enter a search query.")

else:
    # --- Landing Page Content (When no video is loaded) ---
    st.header("Welcome to ActorDB Pro Search!")
    st.markdown("Unlock insights from your video library like never before.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("1. Upload ⬆")
        st.write("Use the sidebar to upload your MP4, AVI, or MOV video file.")
    with col2:
        st.subheader("2. Index 📊")
        st.write("Click *'Index Video Now'* in the sidebar. This analyzes the video's audio and visual content (can take time).")
    with col3:
        st.subheader("3. Search 🔍")
        st.write("Once indexed, use the search bar (which will appear below) to find specific dialogue or scenes.")

    st.info("👈 *Start by uploading a video using the sidebar.*", icon="ℹ")
    # You could add a relevant image here too
    # st.image("path/to/your/intro_image.png")

st.markdown("---")
st.caption("Powered by WhisperX, CLIP, Sentence Transformers, ChromaDB & Streamlit.")