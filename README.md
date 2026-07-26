# VidXP (Video eXPlain) - Video Indexing Engine

**A Python package for video indexing and searching based on audio and scene content.**

## Outline

1. [Product Feature Roadmap Matrix](#product-feature-roadmap-matrix)
2. [Installation](#installation)
3. [Usage](#usage)
4. [Contribution Guidelines](docs/CONTRIBUTING.md)

## Product Feature Roadmap Matrix

|Feature Category|V1 (Basic Features)|V2 (Enhanced Features)|V3 (Advanced Features)|
|----------------|-------------------|----------------------|----------------------|
|**Scene Search**|**Functionality:** Search for scenes based on text description
||**Model:** CLIP (ViT-B/32)
||**Query:** vidxp scene "filepath" "scene description"
|**Dialogue Search**|**Functionality:** Search for specific dialogues and jump to the timestamps
||**Model:** WhisperX (large-v2), SentenceTransformer (all-MiniLM-L6-v2)
||**Query:** vidxp dialogue "filepath" "dialogue"
|**Actor Detection**|**Functionality:** Basic actor detection (making clusters of similar faces)
||**Library:** face_recognition
||**Query:** vidxp face "filepath" "cluster_id"
|**Active Speaker Detection**|**Functionality:** Display active speakers in a scene
||**Model:** TalkNet-ASD
||**Query:** 
|**Actor Search**|N/A
|**User Interface**|CLI + basic GUI
||CLI (Typer) 
||GUI (HTML, CSS, JS)

## Installation

VidXP supports Python 3.10 through 3.13 and requires FFmpeg.

```bash
python -m venv venv
```

Activate the environment:

```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

Install the CLI from PyPI:

```bash
python -m pip install vidxp
```

To include the browser-based Streamlit interface:

```bash
python -m pip install "vidxp[frontend]"
```

`vidxp` is the package name. `frontend` is an optional dependency group that
adds Streamlit; it is not part of the package name.

To install from a source checkout instead, use `python -m pip install .` for the
CLI or `python -m pip install ".[frontend]"` for the CLI and browser interface.

The machine-learning dependencies make the first installation comparatively
large and may require local build tools. See
[INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) for platform requirements and
first-run model downloads.

### Model downloads

Model weights are not stored in this repository. VidXP uses the model identifiers below and lets their libraries download and cache the weights when each capability is first used:

- dialogue embeddings: `sentence-transformers/all-MiniLM-L6-v2`;
- transcription: WhisperX `large-v2`;
- scene search: CLIP `ViT-B/32`;
- language-specific alignment: the default model selected by WhisperX.

The first indexing or search run therefore requires an internet connection and can take longer. Running `vidxp --help` does not load or download models.

## Usage

```bash
vidxp --help
vidxp videoindex samplevideo.mp4
vidxp dialogue "your dialogue query"
vidxp scene "scene description"
vidxp actor 1 samplevideo.mp4
```

Start the frontend with:

```bash
vidxp-ui
```
