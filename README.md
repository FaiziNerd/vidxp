<p align="center">
   <a href ="https://github.com/grayhatdevelopers/vidxp">
      <img src="./docs/images/logo.png" alt="logo" width="200">
   </a>
</p>

<h1 align="center">VidXP</h1>

<p align="center">
  <em>Search video by what was said, what appeared on screen, and recurring faces.</em>
</p>

<p align="center">
  <strong>Dialogue search · Scene search · Actor grouping · CLI · Browser UI · Python API</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/vidxp/">
    <img src="https://img.shields.io/pypi/v/vidxp" alt="PyPI version">
  </a>
  <a href="https://pypi.org/project/vidxp/">
    <img src="https://img.shields.io/pypi/pyversions/vidxp" alt="Supported Python versions">
  </a>
  <a href="https://github.com/grayhatdevelopers/vidxp/actions/workflows/ci.yml?query=branch%3Amain">
    <img src="https://github.com/grayhatdevelopers/vidxp/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI status">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/grayhatdevelopers/vidxp" alt="MIT license">
  </a>
  <a href="https://grayhat.studio/discord">
    <img src="https://img.shields.io/discord/867124708473700363?logo=discord&logoColor=white" alt="Discord">
  </a>
</p>

## Why VidXP

Finding one moment in a video should not require scrubbing through the entire
timeline. VidXP builds a searchable index from three kinds of evidence:

- **Dialogue:** semantic search over timestamped WhisperX transcripts.
- **Scenes:** text-to-frame search using CLIP.
- **Actors:** groups similar detected faces and exports a highlighted video for
  a selected cluster.

After the required model weights are available, video processing and search run
locally. VidXP also saves index state so an incomplete run is not mistaken for a
searchable result.

## Current capabilities

| Capability | Available now | Result |
|---|---|---|
| Dialogue search | Transcription, word alignment, semantic phrase indexing | Matching video time |
| Scene search | Text search over sampled video frames | Matching frame and time |
| Actor grouping | Within-video face detection and clustering | Clustered detections and highlighted output video |
| Interfaces | Typer CLI, Streamlit browser interface, Python API | Interactive or programmatic use |
| Index management | Saved progress, ready/failed state, cancellation, isolated programmatic runs | Traceable and reusable indexes |

## Quick start

VidXP supports Python 3.10 through 3.13 and requires FFmpeg. See the
[installation guide](INSTALLATION_GUIDE.md) for the `dlib` compiler
requirements, source installation, model preparation, and troubleshooting.

Install the command line and browser interface with
[pipx](https://packaging.python.org/en/latest/guides/installing-stand-alone-command-line-tools/).
The command is available on your `PATH` while VidXP and its dependencies remain
isolated:

```bash
pipx install "vidxp[all,frontend]"
```

Install only the capabilities you need with a smaller selection such as
`pipx install "vidxp[scene,frontend]"` or
`pipx install "vidxp[dialogue,scene]"`. To import VidXP from another Python
project, install it into that project's environment instead; the
[installation guide](INSTALLATION_GUIDE.md) covers that path.

Confirm the installed package and its runtime dependencies:

```bash
vidxp --version
vidxp doctor
```

The first use of each capability downloads its model weights. Download the fixed
dialogue, transcription, and scene models in advance with:

```bash
vidxp prepare
```

## Index and search

Build an index containing dialogue, scene, and actor information:

```bash
vidxp index create samplevideo.mp4
```

Search the completed index:

```bash
vidxp search dialogue "the bread just came out of the oven"
vidxp search scene "a yellow taxi on a city street" --top-k 5
vidxp actors list
vidxp actors render 1 samplevideo.mp4
```

Index only selected capabilities or sample fewer visual frames:

```bash
vidxp index create samplevideo.mp4 --modality scene --frame-stride 5
```

Repeat `--modality` to combine `dialogue`, `scene`, and `actor`.
Run `vidxp --help` or any command followed by `--help` for the complete command
reference.

Use named repositories to keep index locations and devices centrally
configured:

```bash
vidxp repositories add team --index-dir ./indexes/team --device cuda --use
vidxp repositories list
```

## Browser interface

Install the `frontend` extra and start:

```bash
vidxp ui
```

The command uses the active named repository, starts a local Streamlit server,
and remains active until stopped.
The interface can upload a video, start or cancel indexing, restore saved
progress after a page reload, and search the capabilities available in the
completed index.

## Use VidXP as a Python package

The programmatic API supports isolated multi-video runs, supplied timestamped
transcripts, resumable per-video checkpoints, and metadata-rich top-k results.

```python
from vidxp.core import IndexConfig, VideoSource
from vidxp.core.runner import run_index
from vidxp.capabilities.scene.operations import search_scene

config = IndexConfig(
    dataset="my-library",
    split="local",
    run_id="demo",
    enabled_modalities=("scene",),
    frame_stride=5,
)

run_index(
    [
        VideoSource(video_id="video-1", path="videos/first.mp4"),
        VideoSource(video_id="video-2", path="videos/second.mp4"),
    ],
    config,
)

results = search_scene("a person enters a taxi", config=config, top_k=5)
for hit in results.hits:
    print(hit.video_id, hit.start, hit.end, hit.score)
```

The [Python indexing and retrieval contract](docs/benchmarking/core_contract.md)
documents configuration, stored metadata, result fields, and run layout.

## Recommended specs

> Coming soon

---


## Current scope

- The standard CLI and browser interface manage one local searchable video
  index at a time. The Python layer supports isolated multi-video runs.
- Actor clusters represent visually similar detected faces; VidXP does not
  automatically know or assign a person's name.
- Model weights are cached separately from the Python package and require
  additional disk space.
- CPU is the current default. Visual indexing processes every frame unless
  `--frame-stride` is configured.
- Search quality depends on the selected models, video domain, speech quality,
  and frame sampling.

## Roadmap

VidXP is an evolving beta. The roadmap extends the current engine rather than
replacing its working search paths.

| Area | Current foundation | Direction |
|---|---|---|
| Search results | Top result in the CLI; structured top-k Python results | Rich ranked results, metadata, previews, and filtering across interfaces |
| Temporal search | Frame and transcript-phrase timestamps | Better time ranges, scene boundaries, aggregation, and ranking |
| Video collections | One local CLI/UI index; isolated multi-video Python runs | User-facing persistent multi-video libraries and index management |
| Actor workflows | Face clustering and highlighted video export | Cluster browsing, labeling, actor search, and stronger tracking |
| Speaker context | Timestamped dialogue search | Active-speaker detection and links between speech and visible people |
| Product experience | CLI and browser indexing/search | Clearer progress, result navigation, recovery, and long-running job controls |
| Evaluation | DiDeMo and HiREST baselines | Combined and component benchmarks, beginning with a LongVALE pilot |

Roadmap items describe intended direction, not a release guarantee.

## Models and local data

| Capability | Model |
|---|---|
| Dialogue embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Transcription | WhisperX `large-v2` |
| Scene search | CLIP `ViT-B/32` |
| Word alignment | WhisperX model selected for the detected language |

VidXP maintains the standard local CLI/UI index in `chroma_data/`. Starting a
new local indexing run replaces the previous or incomplete local index. Model
caches normally live outside this directory and outside the virtual environment.

## Documentation and project links

- [Installation and troubleshooting](INSTALLATION_GUIDE.md)
- [Benchmarking status and results](docs/benchmarking/README.md)
- [Adding a capability](docs/adding-a-capability.md)
- [Changelog](CHANGELOG.md)
- [Issue tracker](https://github.com/grayhatdevelopers/vidxp/issues)
- [MIT license](LICENSE)


## Contributing

See [CONTRIBUTING.md](./docs/CONTRIBUTING.md) for guidelines, maintainers, and how to submit PRs. AI/vibe-coded PRs welcome!

## Credits

Built by Grayhat Developers PVT Ltd in 2025. Maintained by the community.

Email: info@grayhat.studio

<a href="https://github.com/grayhatdevelopers/vidxp/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=grayhatdevelopers/vidxp" />
</a>
