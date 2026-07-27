# Contribution Guidelines

Thanks for contributing to VidXP (Video eXPlain).

## Project layout

| File / path | Role |
|-------------|------|
| `src/vidxp/cli.py` | Typer commands and installed `vidxp` entry point |
| `src/vidxp/application.py` | Reusable application boundary for CLI and future adapters |
| `src/vidxp/capabilities/` | Capability registry, schemas, operations, dependencies, and optional CLI modules |
| `src/vidxp/repositories.py` | Persistent named local-index configuration |
| `src/vidxp/frontend.py` | Streamlit interface launched by `vidxp ui` |
| `src/vidxp/core/` | Capability-neutral storage, media, run state, and execution contracts |
| `src/vidxp/benchmarks/` | Benchmark-specific loaders, prediction adapters, and evaluator calls |
| `pyproject.toml` | Package metadata and Python dependencies |
| `docs/` | Installation-linked guidance, benchmark research, and contribution notes |
| `chroma_data/` | Local ChromaDB index and `index_status.json` readiness record (generated; do not commit) |
| `benchmark_runs/` | Isolated programmatic and benchmark runs (generated; do not commit) |
| Model caches | Managed by WhisperX, SentenceTransformer, and CLIP outside the repository |

The full local CLI/UI index uses up to three collections:
`dialogue`, `scene`, and `actor`. Runs containing
selected capabilities create only the collections they need.

## Setup

Follow the [installation guide](../INSTALLATION_GUIDE.md) or install from the
package metadata directly.

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
python -m pip install -e ".[all,frontend,benchmarks]"
```

Verify the environment:

```bash
vidxp --version
vidxp doctor
```

CLI: `vidxp --help`  
UI: `vidxp ui`

Models default to CPU and download into their libraries' standard caches on
first use. If a model identifier changes, update the setup documentation and
record the exact identifier in benchmark results.

## Where to put work

- Capability-specific indexing, retrieval, models, schemas, and dependencies:
  the matching folder under `src/vidxp/capabilities/`.
- Shared storage, media handling, run state, and execution mechanics:
  `src/vidxp/core/`.
- Transport-neutral application operations: `src/vidxp/application.py`.
- Command-line behavior: `src/vidxp/cli.py`.
- Upload and search UX: `src/vidxp/frontend.py`; keep product logic in the
  shared application and core modules.
- Official benchmark formats and evaluator calls: `src/vidxp/benchmarks/`.
- Capability dependencies: that capability's `requirements.txt`; wire a new
  install extra into `pyproject.toml`.
- Product direction: the roadmap in the main [README](../README.md).

Prefer small, focused pull requests. If you change how embeddings or metadata
are stored, state whether an existing `chroma_data` index must be rebuilt.

## Before you open a PR

1. Run the automated test suite relevant to the change.
2. Index a short sample video, then try dialogue, scene, and—if touched—actor
   search.
3. If you changed the Streamlit app, smoke-test upload, indexing, cancellation,
   reload, and search.
4. Confirm that an incomplete local index is replaced rather than treated as
   ready.
5. Do not commit model weights, generated indexes, benchmark runs, or local
   sample media.

Run the complete automated suite with:

```bash
python -m unittest discover -s tests
```

## Pull requests

- Clear title and a few bullets on what / why.
- Note any new env vars, model downloads, or breaking index format changes.
- Link a related issue when there is one.

## Questions

Follow [Adding a capability](adding-a-capability.md) for the complete extension
contract. Open an issue before large cross-capability refactors so scope stays
aligned with the roadmap.
