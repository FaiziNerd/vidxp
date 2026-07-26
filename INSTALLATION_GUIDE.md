# Installation guide

## Prerequisites

- Python 3.10 through 3.13
- FFmpeg available on `PATH`
- CMake and a C/C++ build toolchain for `dlib`

The official `dlib` releases on PyPI are source distributions. A clean VidXP
installation therefore compiles `dlib` locally on every supported Python
version unless a compatible build is already cached or supplied by the
environment. Changing from Python 3.13 to 3.11 does not avoid this requirement.
On Windows, install CMake and the Microsoft C++ Build Tools. Do not keep
platform-specific wheels in the repository.

## Create an environment

```bash
python -m venv venv
```

```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

## Install from PyPI

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install the command-line package:

```bash
python -m pip install vidxp
```

Install the command-line package and browser interface:

```bash
python -m pip install "vidxp[frontend]"
```

`frontend` is a pip optional dependency group that installs Streamlit. The
package name remains `vidxp`.

## Install from source

From the repository root:

```bash
python -m pip install .
```

Include the Streamlit interface with:

```bash
python -m pip install ".[frontend]"
```

## Installation expectations

VidXP includes PyTorch, WhisperX, computer-vision, and face-recognition
dependencies. The first installation can take time and consume several
gigabytes of disk space. The exact download and installed sizes vary by
operating system, Python version, package versions, and whether CPU or
accelerator-specific packages are selected.

Confirm that both installed entry points start:

```bash
vidxp --help
vidxp doctor
vidxp-ui
```

`vidxp doctor` imports every indexing dependency and checks FFmpeg. It reports
installation problems but does not download model weights.

## Models

VidXP downloads model weights on first use instead of expecting repository-local snapshot directories:

| Capability | Model |
|---|---|
| Dialogue embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Transcription | WhisperX `large-v2` |
| Scene search | CLIP `ViT-B/32` |
| Word alignment | WhisperX default for the detected language |

SentenceTransformer and WhisperX use the Hugging Face cache. CLIP uses its
standard user cache. These downloads are not part of `pip install`. A successful
installation only confirms that VidXP and its Python dependencies are present.
The first `vidxp videoindex` run requires network access for any missing weights
and prepares its models before replacing the previous index.

To download the fixed dialogue, scene, and transcription models ahead of time:

```bash
vidxp prepare
```

WhisperX selects alignment weights after detecting the video's language. Cache a
known alignment language explicitly when needed:

```bash
vidxp prepare --language en
```

Keep that first indexing command, or the terminal running `vidxp-ui`, open until
VidXP reports that the index is ready. Search commands are unavailable until
then. VidXP records indexing progress and the final ready/failed state in
`chroma_data/index_status.json`. The browser interface reloads that status and
the saved `video.mp4` after a page refresh; it does not start a second indexing
run. If the process itself stops before completion, start indexing again. The
restart clears the incomplete single-video index before rebuilding it.

Model caches require additional disk space beyond the Python installation, and
the first use of each capability takes longer while its weights are downloaded.
