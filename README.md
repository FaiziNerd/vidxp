# VidXP

VidXP indexes a video so it can be searched by spoken dialogue, visual scene,
or detected actor. It provides a command-line interface and an optional
browser-based Streamlit interface.

## What it does

- Transcribes speech with WhisperX and searches it with MiniLM embeddings.
- Searches sampled video frames with CLIP.
- Groups similar detected faces and exports videos highlighting a selected
  actor cluster.
- Records indexing progress and prevents searches against incomplete indexes.
- Provides reproducible multi-video indexing and benchmark adapters through its
  Python API.

## Quick start

VidXP supports Python 3.10 through 3.13 and requires FFmpeg. The installation
currently includes actor support, which also requires CMake and a C/C++ build
toolchain because `dlib` is compiled locally.

Create and activate a virtual environment:

```bash
python -m venv venv
```

```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

Install the command-line package:

```bash
python -m pip install vidxp
```

Include the browser interface:

```bash
python -m pip install "vidxp[frontend]"
```

Confirm the installed version and check the runtime dependencies:

```bash
vidxp --version
vidxp doctor
```

See the [installation guide](INSTALLATION_GUIDE.md) for platform prerequisites,
source installation, model downloads, and troubleshooting.

## Index and search a video

Indexing all three supported capabilities:

```bash
vidxp videoindex samplevideo.mp4
```

Search the completed index:

```bash
vidxp dialogue "the bread just came out of the oven"
vidxp scene "a yellow taxi on a city street"
vidxp actor 1 samplevideo.mp4
```

Run `vidxp --help` or a command followed by `--help` for all available options.

To index only selected capabilities or sample fewer visual frames:

```bash
vidxp videoindex samplevideo.mp4 --modalities scene --frame-stride 5
```

`--modalities` accepts any combination of `dialogue`, `scene`, and `actor`.
`--frame-stride N` processes every Nth frame for scene and actor indexing; its
default is `1`.

## Browser interface

Install the `frontend` extra, then start the interface:

```bash
vidxp-ui
```

The command starts a local Streamlit server and remains active until it is
stopped. The interface can upload a video, start or cancel indexing, display
saved progress after a page reload, and search the capabilities present in the
completed index.

## Models and local data

The Python package does not contain the model weights. A model is downloaded and
cached when its capability is first used:

| Capability | Model |
|---|---|
| Dialogue embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Transcription | WhisperX `large-v2` |
| Scene search | CLIP `ViT-B/32` |
| Word alignment | WhisperX model selected for the detected language |

Download the fixed models before the first indexing run with:

```bash
vidxp prepare
```

Add a language code to prepare a WhisperX alignment model as well:

```bash
vidxp prepare --language en
```

VidXP maintains one local searchable index at a time in `chroma_data/`. Starting
a new local indexing run replaces the previous or incomplete local index.

## Development and benchmarking

- [Contribution guidelines](docs/CONTRIBUTING.md)
- [Benchmarking status and results](docs/benchmarking/README.md)
- [Benchmark-ready Python API](docs/benchmarking/core_contract.md)
