# Official adapter validation ledger

This ledger records the implementation and executable validation of the first
two benchmark adapters. Subset runs are smoke tests of the complete data,
indexing, serialization, and evaluator path. Their metrics are not paper scores.

## Pinned official artifacts

| Benchmark | Artifact | Revision | SHA-256 |
|---|---|---|---|
| DiDeMo | [`data/test_data.json`](https://github.com/LisaAnne/LocalizingMoments/blob/b6a555c8134581305d0ed4716fbc192860e0b88c/data/test_data.json) | `b6a555c8134581305d0ed4716fbc192860e0b88c` | `1891c04ec48b3d364c739594b2b6413806b74bd9027c092d896e7ebb930ff1cd` |
| DiDeMo | [`utils/eval.py`](https://github.com/LisaAnne/LocalizingMoments/blob/b6a555c8134581305d0ed4716fbc192860e0b88c/utils/eval.py) | `b6a555c8134581305d0ed4716fbc192860e0b88c` | `4754bb320564e5d2e7c633e0b660e87feca7f00fa73269e50140e81ffb4ca762` |
| HiREST | [`data/splits/all_data_test.json`](https://github.com/j-min/HiREST/blob/deffc169b4e8d51c1589d5512ad05da61e81bcee/data/splits/all_data_test.json) | `deffc169b4e8d51c1589d5512ad05da61e81bcee` | `00219050c022ff2fc89c210ca4db605de6aa13c5c6014e4c678345ade3448a62` |
| HiREST | [`data/evaluation/categories.json`](https://github.com/j-min/HiREST/blob/deffc169b4e8d51c1589d5512ad05da61e81bcee/data/evaluation/categories.json) | `deffc169b4e8d51c1589d5512ad05da61e81bcee` | `157623d50f7b8482f55fa1c4efc500539784c0399fb2dd60bb687b4006d85ca1` |
| HiREST | [`evaluate.py`](https://github.com/j-min/HiREST/blob/deffc169b4e8d51c1589d5512ad05da61e81bcee/evaluate.py) | `deffc169b4e8d51c1589d5512ad05da61e81bcee` | `c4b8ba9b572ae4088e90ddc3eec2b2cc4f5b4c1a0153ff6e0843817da89a5ca0` |
| HiREST | [`ASR.zip`](https://huggingface.co/j-min/HiREST-baseline/resolve/54e2f8da7a4384fec8a137011399f5e104069032/ASR.zip) | `54e2f8da7a4384fec8a137011399f5e104069032` | `0b452d38e30064dc7273a58b7b73ec33e307ff83d30048a472777f56e3a29fbc` |

The adapters verify these hashes before indexing. Each run manifest also records
the artifact paths, URLs, revisions, sizes, and observed hashes. VidXP does not
replace the official downloaders; the adapters consume prepared media and ASR.

## Validated official split facts

The pinned DiDeMo test split contains 4,021 annotations over 1,037 videos. Of
these, 473 annotations over 122 videos declare `num_segments: 5`; their labels do
not use chunk 5.

The pinned HiREST test split contains 546 prompts. Moment retrieval evaluates
exactly 776 `clip: true` prompt/video pairs across 382 prompts and 776 unique
videos. Every one of those videos has a matching SRT in the pinned released-ASR
archive. Entries with `clip: false` do not enter the moment-retrieval adapter.

## DiDeMo behavior

1. Verify and read the official annotation file.
2. Index each selected video through the scene-only core.
3. Search every selected annotation against all sampled frames of its known
   video.
4. Ignore frames at or after 30 seconds, average frame scores inside each of the
   six five-second chunks, and average the included chunk scores for each moment.
5. Rank the official candidate set: six single chunks followed by the 15
   `(start, end)` combinations defined in the official repository.
6. For five-segment videos, rank all 15 available moments before the six moments
   involving unavailable chunk 5. All 21 candidates remain in the file because
   the official evaluator requires 21 predictions per annotation.
7. Reject missing, duplicate, illegal, or misordered candidates before writing
   `predictions.json`.
8. Invoke the pinned evaluator.

The evaluator is Python 2 source. The compatibility runner loads that pinned
source and changes only its three `print` statements to Python 3 syntax. Its
rank and IoU expressions are not copied or altered. `evaluator.log` records the
command, working directory, compatibility note, output, and return code.

## HiREST released-ASR behavior

1. Verify the test split, categories, evaluator, and released-ASR archive.
2. Select only declared `clip: true` prompt/video pairs.
3. Parse the matching released SRT files with the `srt` package.
4. Submit timestamped segments to the dialogue-only VidXP core. The run uses
   MiniLM and does not load WhisperX or decode video.
5. Search each prompt only within its known video and retain the top interval.
6. Clamp the interval to the official video duration, then reject missing,
   non-finite, zero-length, negative, or structurally invalid predictions.
7. Serialize the exact nested official form:

   ```json
   {
     "prompt": {
       "video.mp4": {
         "bounds": [12.0, 18.5]
       }
     }
   }
   ```

8. Invoke the unchanged official evaluator with
   `--task moment_retrieval`.

The evaluator imports `language_evaluation` at module load although moment
retrieval never references it. The adapter supplies an empty temporary import
shim for that unused captioning dependency. The official file and moment metric
logic remain unchanged, and the shim is disclosed in `evaluator.log`.

## Commands

Install the optional adapter parser:

```powershell
python -m pip install -e ".[benchmarks]"
```

Run a declared DiDeMo smoke subset by zero-based official annotation indices:

```powershell
vidxp benchmark didemo `
  --annotations <LocalizingMoments>/data/test_data.json `
  --evaluator <LocalizingMoments>/utils/eval.py `
  --media-directory <didemo-videos> `
  --annotation-indices 0,1,2 `
  --run-id didemo-smoke
```

Omit `--annotation-indices` for the full official test split.

For HiREST, a smoke pair file is a JSON list:

```json
[
  {
    "prompt": "Make DIY Office Weapons",
    "video": "nWBuM3LNTcM.mp4"
  }
]
```

Run the declared pair subset:

```powershell
vidxp benchmark hirest `
  --ground-truth <HiREST>/data/splits/all_data_test.json `
  --categories <HiREST>/data/evaluation/categories.json `
  --evaluator <HiREST>/evaluate.py `
  --asr-archive <downloads>/ASR.zip `
  --asr-directory <extracted>/ASR `
  --pairs <subset-pairs.json> `
  --run-id hirest-smoke
```

Omit `--pairs` for all 776 official moment pairs.

## Shared run output

Both adapters produce:

```text
benchmark_runs/<benchmark>/<run_id>/
  manifest.json
  predictions.json
  metrics.json
  timings.jsonl
  failures.jsonl
  evaluator.log
  index/
```

They also retain `ground_truth.subset.json`, the core completion marker, and
per-video checkpoints. Empty failure logs are created deliberately.

## 2026-07-27 executable smoke results

| Adapter | Declared subset | Actual path exercised | Official evaluator result |
|---|---|---|---|
| DiDeMo | Test annotation index `0`; one official downloaded video; frame stride `30` | Real CLIP scene indexing, 21-candidate aggregation, strict serialization, pinned evaluator | Rank@1 `0.0`, Rank@5 `1.0`, mIoU `0.0` |
| HiREST | `Make DIY Office Weapons` / `nWBuM3LNTcM.mp4` | Released SRT parsing, real MiniLM/Chroma dialogue indexing, top-1 known-video interval, pinned evaluator | one video; R@0.5 `0.0`, R@0.7 `0.0` |

The zero values are retained because they are what the official evaluators
returned for these one-item smoke subsets. They establish execution and format
correctness only.

The first HiREST evaluator run returned successfully, but VidXP's output parser
rejected the evaluator's `np.float64(...)` representation. The parser was
limited to normalizing those NumPy scalar wrappers, covered by a regression
test, and the same run then completed with an empty `failures.jsonl`. No metric
value or prediction was changed.
