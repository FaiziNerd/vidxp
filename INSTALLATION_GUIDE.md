# Installation guide

## Prerequisites

- Python 3.10 through 3.13
- FFmpeg available on `PATH`
- A C/C++ build toolchain if pip needs to compile `dlib`

On Windows, install the Microsoft C++ Build Tools if no compatible `dlib` wheel is available. Do not keep platform-specific wheels in the repository.

## Environment

```bash
python -m venv venv
```

```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

```bash
python -m pip install --upgrade pip
python -m pip install ".[frontend]"
```

Confirm that both installed entry points start:

```bash
vidxp --help
vidxp-ui
```

## Models

VidXP downloads model weights on first use instead of expecting repository-local snapshot directories:

| Capability | Model |
|---|---|
| Dialogue embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Transcription | WhisperX `large-v2` |
| Scene search | CLIP `ViT-B/32` |
| Word alignment | WhisperX default for the detected language |

SentenceTransformer and WhisperX use the Hugging Face cache. CLIP uses its standard user cache. These downloads are not part of `pip install`, so the first indexing or search operation requires network access.
