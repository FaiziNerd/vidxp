# Contribution Guidelines

Thanks for contributing to VidXP (Video eXPlain).

## Project layout

| File / path | Role |
|-------------|------|
| `main.py` | Typer CLI and core pipeline (`videoindex`, `dialogue`, `scene`, `actor`) |
| `frontend.py` | Streamlit UI that calls those same functions |
| `requirements.txt` | Python dependencies |
| `docs/` | Design notes and guides (including this file) |
| `chroma_data/` | Local ChromaDB index (generated; do not commit) |
| Model / cache dirs | Local WhisperX, SentenceTransformer, CLIP weights (do not commit) |

Indexing writes three collections: `voiceEmbeddings`, `sceneEmbeddings`, and `actorCollection`.

## Setup

Follow `Installation Guide.txt` (Windows often needs a local `dlib` wheel before `pip install -r requirements.txt`).

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

CLI: `python main.py --help`  
UI: `streamlit run frontend.py`

Models default to CPU in `main.py`. Point local model paths at your machine, or document path changes in the PR.

## Where to put work

- Pipeline, retrieval, or face clustering: `main.py`
- Upload / search UX: `frontend.py` (keep it thin; reuse CLI functions)
- New dependencies: update `requirements.txt` and note why in the PR
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
