# Installation guide

The main [README](README.md) introduces the product and contains the shortest
install-and-run path. This guide covers platform prerequisites, source
installation, model preparation, and common first-run issues.

## Prerequisites

- Python 3.10 through 3.13
- FFmpeg available on `PATH`
- CMake and a C/C++ build toolchain for `dlib`

The official `dlib` package is distributed through PyPI as source. Installing
VidXP therefore compiles it locally unless a compatible build is already cached
or provided by the environment. Changing from Python 3.13 to 3.11 does not
remove that requirement.

On Windows, install CMake and the Microsoft C++ Build Tools. Do not add
platform-specific `dlib` wheels to this repository.

## Create an environment

Using a virtual environment keeps VidXP and its Python dependencies separate
from the system Python:

```bash
python -m venv venv
```

```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

Upgrade pip before installing:

```bash
python -m pip install --upgrade pip
```

## Install from PyPI

Install the command-line package:

```bash
python -m pip install vidxp
```

Install the command-line package and Streamlit interface:

```bash
python -m pip install "vidxp[frontend]"
```

`frontend` is an optional dependency group. The package name remains `vidxp`.

## Install from source

From the repository root:

```bash
python -m pip install .
```

Include the Streamlit interface:

```bash
python -m pip install ".[frontend]"
```

Use an editable installation while developing:

```bash
python -m pip install -e ".[frontend,benchmarks]"
```

## Verify the installation

Display the installed package version:

```bash
vidxp --version
```

Check FFmpeg and the Python dependencies needed by all indexing capabilities:

```bash
vidxp doctor
```

`vidxp doctor` imports the selected dependencies but does not download model
weights. Restrict the check when diagnosing one capability:

```bash
vidxp doctor --modalities scene
```

If the frontend extra was installed, start the interface with `vidxp-ui`. It
runs until stopped with `Ctrl+C`.

## Prepare models

Model weights are not part of the Python package:

| Capability | Model |
|---|---|
| Dialogue embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Transcription | WhisperX `large-v2` |
| Scene search | CLIP `ViT-B/32` |
| Word alignment | WhisperX model selected for the detected language |

Download and cache the fixed dialogue, transcription, and scene models before
indexing:

```bash
vidxp prepare
```

WhisperX selects its alignment model after detecting the video's language. Cache
a known language explicitly when required:

```bash
vidxp prepare --language en
```

SentenceTransformer and WhisperX use the Hugging Face cache; CLIP uses its own
user cache. These caches normally live outside the virtual environment, so
removing the environment does not necessarily remove downloaded model weights.

## First indexing run

A successful installation means the commands and Python dependencies are
available. It does not mean the model weights have been downloaded.

If `vidxp prepare` was not run first, the initial indexing command downloads any
missing models before processing the video:

```bash
vidxp videoindex samplevideo.mp4
```

Keep the terminal and internet connection open until VidXP reports that the
index is ready. Machine-learning dependencies and model caches can consume
several gigabytes, and the first run takes longer while models are downloaded.
Exact sizes depend on the platform and selected package builds.

VidXP saves local progress and the final state in
`chroma_data/index_status.json`. Search is unavailable until indexing completes.
If the process stops early, run indexing again; VidXP clears the incomplete
single-video index before rebuilding it.

## Common problems

### `dlib` fails to install

Confirm that CMake and a working C/C++ compiler are installed and visible from
the active terminal. On Windows, use the Microsoft C++ Build Tools.

### FFmpeg is not found

Run `ffmpeg -version` in the same terminal. Install FFmpeg or add its executable
directory to `PATH`, then rerun `vidxp doctor`.

### A search says the index is not ready

Wait for the active indexing command to finish. If the previous process ended
or failed, run `vidxp videoindex` again to rebuild the incomplete local index.

### The first indexing run appears slow

Check the terminal for model-download or indexing progress. Model preparation,
transcription, scene analysis, and actor detection are separate stages. Use
`vidxp prepare` before indexing or select fewer capabilities with
`--modalities`.
