# Contribution Guidelines

Thanks for contributing to VidXP (Video eXPlain).

## Project layout

| File / path | Role |
|-------------|------|
| `src/vidxp/main.py` | Typer CLI and core pipeline (`videoindex`, `dialogue`, `scene`, `actor`) |
| `src/vidxp/frontend.py` | Streamlit UI that calls those same functions |
| `pyproject.toml` | Package metadata and Python dependencies |
| `docs/` | Design notes and guides (including this file) |
| `chroma_data/` | Local ChromaDB index (generated; do not commit) |
| Model / cache dirs | Local WhisperX, SentenceTransformer, CLIP weights (do not commit) |

Indexing writes three collections: `voiceEmbeddings`, `sceneEmbeddings`, and `actorCollection`.

## Setup

Follow `INSTALLATION_GUIDE.md` or install from the package metadata directly.

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install ".[frontend]"
```

CLI: `vidxp --help`  
UI: `streamlit run src/vidxp/frontend.py`

Models default to CPU in `main.py`. Point local model paths at your machine, or document path changes in the PR.

## Where to put work

- Pipeline, retrieval, or face clustering: `main.py`
- Upload / search UX: `frontend.py` (keep it thin; reuse CLI functions)
- New dependencies: update `pyproject.toml` and note why in the PR
- Roadmap items (see README): active speaker detection, richer actor search, stronger GUI

Prefer small, focused PRs. If you change how embeddings or metadata are stored, say whether existing `chroma_data` must be wiped and re-indexed.

## Before you open a PR

1. Index a short sample video, then try dialogue, scene, and (if touched) actor search.
2. If you changed the Streamlit app, smoke-test upload, index, and search.
3. Do not commit: model weights, `chroma_data/`, sample videos, `audio.wav`, `video.mp4`, or `output.mp4`.

## Pull requests

- Clear title and a few bullets on what / why.
- Note any new env vars, model downloads, or breaking index format changes.
- Link a related issue when there is one.

## Questions

Open an issue before large refactors or new modalities so scope stays aligned with the roadmap.
