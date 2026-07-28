# Runtime validation ledger

This ledger records executable checks for the benchmark-ready core. It is
separate from unit-test coverage and from benchmark results. A smoke result here
must not be reported as a paper score.

## 2026-07-27 Chunk 1 closure

### Failure that triggered the pass

A Streamlit source server that remained alive across code changes re-executed
`frontend.py` while resolving a mismatched `index_worker` module. The frontend
then failed while importing the newly added `can_cancel_indexing` symbol.

The fix removed that unnecessary helper boundary. The UI now uses the existing
`cancel_indexing()` result directly. This avoids requiring a newly added
cross-module symbol merely to decide whether the cancel button should render.

A separate clean browser run also showed why the following command is unsafe in
an environment that already contains a different VidXP installation:

```powershell
python -m streamlit run .\src\vidxp\frontend.py
```

Without selecting the local `src` package, that command can execute the source
frontend against the installed package. The validated source-tree command is:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
python -m streamlit run .\src\vidxp\frontend.py
```

For an installed wheel, the supported command remains:

```powershell
vidxp ui
```

### Real execution checks

All commands below used the Python 3.13 project test environment on Windows.
Generated clips, run directories, and wheel environments were created under a
temporary directory. The repository's `video.mp4`, `audio.wav`, local index, and
ready status were not modified. Source checks explicitly set
`PYTHONPATH` to the repository's `src` directory; omitting it in this environment
selects the older installed TestPyPI package instead.

| Check | Executed path | Observed result |
|---|---|---|
| Source Streamlit UI | Source selected through `PYTHONPATH`, real browser session | Page rendered with upload, index, status, and search controls; no import exception |
| Built-wheel UI | Fresh wheel installed without VidXP source on its import path; browser interface opened from the installed package | Page rendered successfully and the Streamlit health endpoint returned `ok` |
| Built-wheel CLI | Final wheel installed into an isolated target while using the validated dependency environment; wheel target placed first on `PYTHONPATH` | Import resolved inside the wheel target and `python -m vidxp --help` listed the expected commands |
| Dependency doctor | `vidxp doctor --modalities dialogue,scene,actor` | ChromaDB, MiniLM, CLIP, NumPy, OpenCV, Pillow, PyTorch, face recognition, MoviePy, WhisperX, and FFmpeg imports resolved |
| Released-transcript path | Real MiniLM encoding, Chroma writes, and top-2 dialogue search over three timestamped segments | Run completed; two hits returned; first interval was `[0.0, 2.0]`; full run/source metadata present |
| Raw-video dialogue path | Five-second derived video with audio, real WhisperX `large-v2`, English alignment, MiniLM, and Chroma writes | Language detected as English; four dialogue phrases indexed; run state completed |
| Scene-only path | Four-frame derived clip, real CLIP encoding and Chroma search | Four frames indexed; two hits returned; neither WhisperX nor face recognition loaded |
| Actor-only path | Same derived clip, real face detection/clustering | Four frames indexed; eight detections retained |
| Shared visual path | Same clip with scene and actor enabled | Four source frames advanced once; four scene and four actor frame operations recorded |
| Multiprocessing worker | Actual Windows spawned child with an immediately failing missing input | Child target imported and ran; process lifecycle returned to inactive |
| Actor result export | Four-frame derived clip rendered with one structured detection to a nested temporary output path | Output directory was created; `avc1` failed in the local OpenCV build, `mp4v` fallback succeeded, and the 63,686-byte four-frame MP4 reopened successfully |
| Automated suite | Source selected through `PYTHONPATH`; `python -m unittest discover -s tests` | 71 tests passed |
| Distribution build | `python -m build` | Source distribution and wheel completed successfully |

### Confirmed fixes from this pass

- Actor export now creates the destination directory, rejects identical
  input/output paths, validates the source capture and FPS/dimensions, checks the
  video writer, falls back from `avc1` to `mp4v` when necessary, and verifies a
  non-empty output before reporting success.
- `IndexConfig` normalizes `Path` values supplied for output/storage locations so
  manifests remain JSON serializable.
- The cancellation UI no longer relies on the hot-reload-fragile helper described
  above.

### Harness observations

An initial raw-video harness accidentally created an audio-only MP4, which
MoviePy correctly rejected because it had no video frame rate. A subsequent run
completed indexing, then the harness tried to delete the temporary Chroma
directory before its SQLite handle had closed. The final validation retained the
temporary directory until process exit and completed cleanly. Neither harness
mistake is reported as a VidXP failure.
