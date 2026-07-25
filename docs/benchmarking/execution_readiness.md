# Benchmark execution readiness

Collection index: [Benchmarking research](README.md)

Status: Corrected implementation assessment

Established: 2026-07-26

Baseline before this reassessment: commit `4607f9d`

## Corrected premise

VidXP's current return shape is not a fixed research constraint. The implementation
may be changed to support published benchmark protocols when the change is ordinary
engineering rather than a new learned capability.

Allowed benchmark plumbing includes:

- stable dataset, split, run, video, clip, frame, phrase, and face-track IDs;
- configurable top-k results instead of top-1;
- raw distances plus a documented monotonic score;
- start and end timestamps, frame/shot boundaries, and supplied metadata;
- collection namespaces and dataset/video filters;
- deterministic point-to-clip, point-to-window, shot, or video aggregation;
- temporal de-duplication or non-maximum suppression;
- fixed sliding-window proposals;
- benchmark-specific prediction serializers and evaluator invocation;
- non-learned score or rank fusion over existing scene and dialogue outputs;
- modality-specific indexing, batching, resumability, and timing instrumentation.

These changes do not alter the benchmark task and do not invalidate comparison with
published baselines.

Material capability changes remain separate:

- training or fine-tuning a retrieval or temporal-localization model;
- adding OCR, generic sound-event recognition, speaker diarization/identification,
  learned fusion, or a multilingual replacement encoder;
- adding face/body/voice fusion or a new actor-tracking model.

A benchmark may still be run when VidXP lacks one evidence channel. Unsupported
queries can remain in the official denominator and produce poor scores. The result
must describe the missing capability; it must not claim full modality coverage.

## Repository complexity finding

The current system is not protected by a complex package API. It is a small
application centered on `main.py`, with direct Typer commands and a thin Streamlit
caller in `frontend.py`.

The main benchmark-facing limitations are localized:

- numeric Chroma IDs restart for every video;
- voice records store only `start`;
- scene records store only `time`;
- search hardcodes `n_results=1` and discards distances;
- indexing always runs dialogue, scene, and actor work together;
- frame inference and database writes are unbatched;
- WhisperX is loaded inside each indexing call;
- no dataset/run namespace or benchmark serializer exists.

Nothing in that list requires a new model.

## Classification used from this point

Benchmark fit and execution state are separate:

| Axis | Class | Meaning |
| --- | --- | --- |
| Engineering | **A — adapter** | Valid official predictions can be produced with existing encoders plus deterministic plumbing |
| Engineering | **B — material** | A faithful claim requires a new model, learned method, or new product capability |
| Operations | **Ready** | Public artifacts are sufficient to begin a smoke run |
| Operations | **Gated** | Agreement, license, media survival, storage, or compute must be resolved |
| Operations | **Blocked** | A necessary corpus, evaluator, or artifact is not presently obtainable |

“A/Ready” does not mean VidXP will score well. It means the official evaluator can
measure the current method without changing the task.

## Shared implementation slice

The minimum reusable retrieval result is:

```text
query_id -> [
  {
    video_id,
    start,
    end,
    score,
    raw_distance,
    modality,
    source_id
  },
  ...
]
```

The minimum indexing changes are:

1. Split audio, scene, and actor indexing into selectable functions.
2. Accept `dataset`, `split`, `run_id`, and stable `video_id`.
3. Use collision-safe IDs such as
   `run_id:video_id:modality:local_index`.
4. Store voice `{start, end, text, video_id}` and scene
   `{frame_index, time, video_id, fps, duration}`.
5. Make `top_k`, collection name, and optional `video_id` filter configurable.
6. Return ordered records with metadata, distances, and scores.
7. Batch model inference and Chroma writes and reuse loaded models.
8. Add fixed aggregation and serialization outside the core encoder code.

A scene-only implementation slice is approximately one to two developer days. A
reusable scene/dialogue/corpus contract with tests, batching, and serializers is
approximately three to five developer days. Dataset download and indexing time are
not included.

## Revised executable shortlist

| Benchmark | Engineering | Operations | What is executable |
| --- | --- | --- | --- |
| DiDeMo | A, small | Ready | Official 21-candidate moment ranking with Rank@1/5 and mean IoU |
| HiREST | A, small | Ready for released ASR | Official speech-backed instructional video and moment retrieval using VidXP chunking, MiniLM, Chroma, and released transcripts |
| QVHighlights | A, medium | Gated by 133.9 GiB raw archive/CPU cost | Official interval retrieval and two-second clip saliency on an explicitly named annotation/test release |
| Charades-STA | A, medium | Gated by data agreement | Official ranked interval retrieval using fixed-grid windows on either the labelled original or filtered split |
| MSR-VTT | A, small | Ready after media preparation | Official whole-video text retrieval from pooled frame scores |
| QuerYD | A, small/medium | Ready for transcript/oracle-proposal mode; narration audio unresolved | Official paragraph-video and supplied-proposal retrieval now; unrestricted boundaries are not the paper protocol |
| TVR `sub-only`, `video-only`, `video+sub` | A, medium | Gated by lawful raw TV clips with audio | Official SVMR/VCMR/VR once media exists |
| TVR-Ranking | A after TVR | Gated by TVR media and exact license | Official graded ranked moment retrieval |
| BCL on BBT/Buffy | A/medium evaluator adapter | Gated by lawful episode media | Official WCP/NMI after mapping VidXP detections or tracks to benchmark instances |
| LongVALE | A/medium with fixed late fusion | Gated by about 254 GB and raw-media survival | Official temporal grounding using existing vision and speech rankings; no generic-audio claim |
| FLARE | A/medium | Ready, about 71 GB | Official caption-to-clip/video retrieval and clip-level simulated-query retrieval; unsupported sound-only queries remain measured failures |
| TRECVID AVS | A/medium | Gated by agreement and roughly 1.6 TB V3C2 | Archived 2024/2025 top-1,000 master-shot ranking and mean xinfAP using exact-year topics/qrels |
| MultiVENT 2.0 | A/large operational adapter | Gated by about 1.93 TB and compute | Official ranked-video run using scene, ASR, and supplied descriptions; embedded-text/OCR unsupported and generic acoustic audio is not a benchmark channel |
| VectorDBBench | A, small | Ready | Chroma recall, indexing time, latency, and QPS diagnostic only |

## Benchmark-specific corrections

### DiDeMo

DiDeMo is not blocked by point timestamps. VidXP can score frames, aggregate them
into the six published five-second chunks, score all 21 legal contiguous moments,
and emit the official ranked list. No temporal model is needed.

This remains the first visual benchmark because it validates nearly all shared
scene infrastructure at low cost.

### HiREST

HiREST is executable immediately in transcript-backed mode:

1. ingest the released ASR and timestamps;
2. rechunk and embed it with VidXP's MiniLM path;
3. aggregate phrase hits by `video_id` for video retrieval;
4. use the top phrase's `[start, end]` in the known video for moment retrieval;
5. serialize predictions to the official evaluator.

This measures VidXP's chunking, embedding, vector indexing, and retrieval while
holding ASR constant. A later raw-video run adds WhisperX after a full YouTube
survival audit. The official baseline's use of Whisper and
`all-MiniLM-L6-v2` makes this a particularly useful same-stack benchmark.

### QVHighlights and Charades-STA

Both can be evaluated without a learned proposal model. Fixed clip grids or
predeclared multi-scale windows produce valid non-zero intervals. Deterministic
aggregation and temporal NMS are baseline logic, not benchmark manipulation.

QVHighlights' main issue is download/indexing cost. Charades-STA's main issue is
the dataset agreement and its narrow staged-indoor domain.

### TVR and TVR-Ranking

These are algorithmically compatible after the shared corpus adapter. The real
blocker is raw copyrighted media with original audio, not top-k or interval output.
If lawful media is secured, run `t`, `v`, and `vt` separately and preserve the
official evaluator.

### QuerYD

The released transcript/proposal task is executable with current models. The
end-to-end narration-audio claim remains pending because the narration WAV endpoint
was not confirmed at file level. Narration rather than in-scene dialogue is a
scientific caveat, not an implementation blocker.

### Actor clustering

The actor lane has a different external constraint. VidXP can emit per-detection
cluster IDs and an evaluator adapter can assign each benchmark face track to a
predicted cluster using timestamp/bounding-box matching and a frozen majority rule.
That is ordinary evaluation plumbing.

BCL still needs lawful raw BBT/Buffy episodes to test VidXP's own dlib embeddings.
Running BCL only on its supplied SE-ResNet features verifies the evaluator but does
not evaluate VidXP. Hannah remains a viable end-to-end alternative if its research
agreement and movie access are approved.

### LongVALE and FLARE

Fixed late fusion over existing scene and dialogue rankings is permitted baseline
logic. It makes official retrieval or temporal-grounding runs technically possible.
VidXP still lacks generic sound-event recognition; the result must say so and must
not be described as full omni-modal coverage.

LongVALE is the stronger peer-reviewed combined benchmark. FLARE is the cheaper
pilot but remains a 2026 preprint with model-generated, rank-filtered queries.

### Large-corpus tests

TRECVID and MultiVENT are technically executable after adapters. Their present
deferral is operational: agreements, terabyte-scale storage, resumable ingestion,
and current CPU-only runtime. API shape is no longer listed as the blocker.

## Immediate execution path

1. Implement and test the shared stable-ID, interval, top-k, score, filter, and
   serializer contract.
2. Run a small DiDeMo smoke set, then its full validation protocol.
3. In parallel, run HiREST's released-ASR video and moment retrieval protocols.
4. Add the local timing harness and VectorDBBench diagnostic while those corpora
   index.
5. Resolve TVR and actor raw-media access before writing those adapters.
6. Move to QVHighlights validation after confirming the storage/runtime budget.
7. Treat LongVALE and FLARE as combined follow-ups, with modality limitations
   declared in advance.

This order yields official metrics quickly while keeping the preferred but
access-gated TVR and BCL targets active.
