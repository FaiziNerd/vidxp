# Published benchmark catalog

Collection index: [Benchmarking research](README.md)

Status: Discovery complete; execution readiness reassessed

Last verified: 2026-07-25

Scope: Current VidXP implementation in `main.py`

This catalog is the working decision record for published benchmarks. It is not a
claim that VidXP has been run on any of them. Published results become comparable
baselines only after VidXP and the competing method use the same data, task,
prediction unit, and evaluator.

## Decision summary

There is no credible single benchmark that directly exercises the current dialogue
retrieval, scene retrieval, and actor clustering paths together.

The current top-1 point API is not a meaningful blocker. Stable IDs, top-k results,
scores, start/end timestamps, extra metadata, deterministic interval aggregation,
filters, and serializers are lightweight benchmark engineering. The repository is
a small `main.py` application rather than a complex public API surface.

The smallest credible suite is therefore component-based:

1. **DiDeMo** as the first, inexpensive scene-retrieval smoke benchmark.
2. **HiREST with released ASR** as the first executable dialogue/video retrieval
   benchmark.
3. **QVHighlights** as the stronger variable-duration scene benchmark.
4. **TVR `t` queries** as the preferred dialogue benchmark if lawful clips with
   audio are obtainable; otherwise use **HiREST** and **QuerYD** as speech-backed
   component tests and state their semantic mismatch.
5. **BCL on BBT/Buffy** as the best reproducible actor-clustering protocol, provided
   the team can obtain the underlying episodes or explicitly limits the experiment
   to BCL's supplied features.
6. **LongVALE** as a combined vision–speech temporal test using a frozen,
   non-learned fusion rule while clearly disclosing unsupported generic audio.
7. A fixed local indexing/query timing protocol, reported as a VidXP engineering
   measurement rather than as a score directly comparable with unrelated hardware.

LongVALE is the strongest peer-reviewed combined vision–audio–speech temporal
benchmark found. It still omits actor clustering and expects genuinely fused
multi-modal interval predictions. A fixed rank/score fusion adapter makes an
official run possible without claiming full omni-modal coverage. FLARE is a smaller
downloadable audio-visual stress test, but it is a 2026
preprint benchmark with generated, filtered queries. It belongs in a secondary
experiment or watchlist until peer review and benchmark stability improve.

See [execution readiness](execution_readiness.md) for the corrected implementation
boundary and per-benchmark engineering classification.

## Verdict meanings

- **Directly runnable:** no task-definition changes are needed.
- **Adaptable:** official data or evaluation is usable after a narrow, documented
  output adapter.
- **Reference-only:** useful context, but not a valid executable comparison under
  present access or artifact conditions.
- **Irrelevant:** does not evaluate an implemented VidXP capability.

## What every identified benchmark can tell us

This is the interpretation table for the complete candidate inventory. “Tells us”
means the conclusion supported by running VidXP through the stated official
protocol. It does not mean that a similar published score is already comparable.

| Category | Benchmark or protocol | Capability actually measured | What a VidXP result would tell us | What it would **not** tell us | Current status |
| --- | --- | --- | --- | --- | --- |
| Dialogue | [TVR `t` queries](https://github.com/jayleicn/TVRetrieval) | Transcript-related query to ranked video intervals, both known-video and corpus-wide | Whether WhisperX/MiniLM dialogue evidence can identify and temporally localize relevant TV moments; a subtitle-only run isolates embedding and retrieval | Scene understanding, actor clustering, generic audio, or end-to-end ASR quality when supplied subtitles are used | Engineering A; raw TV media gated |
| Visual | [TVR `v` queries](https://github.com/jayleicn/TVRetrieval) | Visual-language query to ranked video intervals | Whether frame/clip CLIP evidence can retrieve visual moments across a TV corpus | Dialogue retrieval, actor identity, or performance on non-TV domains | Engineering A; raw TV media gated |
| Combined | [TVR `vt` queries](https://github.com/jayleicn/TVRetrieval) | Queries requiring both visual and subtitle evidence | Whether fixed late fusion improves corpus moment retrieval when both implemented paths contain useful evidence | Generic sound understanding, actor clustering, or learned cross-modal reasoning | Engineering A with fixed fusion; raw TV media gated |
| Dialogue/system | [HiREST](https://github.com/j-min/HiREST) | Instructional query to ranked videos and a relevant interval | Whether VidXP's chunking, MiniLM embeddings, vector index, and interval selection retrieve semantically relevant spoken procedural content | Verbatim dialogue search, entertainment-video generalization, actors, or WhisperX accuracy in released-ASR mode | Engineering A; released-ASR mode ready |
| Dialogue | [QuerYD](https://www.robots.ox.ac.uk/~vgg/data/queryd/) | Description-to-video/proposal retrieval using narrated audio descriptions | Whether speech/text indexing can rank the correct narrated video segment or proposal | In-scene conversational dialogue, overlapping speech, scene-only search, or free boundary prediction under the oracle-proposal protocol | Engineering A for transcript/proposal mode; narration audio unresolved |
| Ranked search | [TVR-Ranking](https://huggingface.co/axgroup/TVR-Ranking) | Graded ranking of multiple relevant corpus moments for imprecise queries | Whether VidXP orders several partially relevant moments usefully, not merely whether its top result overlaps one answer | ASR quality when subtitles are supplied, actors, or generalization outside TVR | Engineering A after TVR; media/license gated |
| Spoken retrieval | [TREC Podcasts](https://trecpodcasts.github.io/) | Semantic query to graded, timestamped long-form spoken segments | Whether VidXP can rank relevant spoken passages across a large audio corpus | Visual retrieval, video timing beyond fixed segments, or actor clustering | Reference-only; corpus access closed |
| Spoken occurrence | [NIST OpenKWS](https://www.nist.gov/document/openkws13-evalplan-v4pdf) | Detection of every exact spoken keyword occurrence with calibrated accept/reject decisions | Miss, false-alarm, timing, threshold-calibration, indexing-time, and search-time behavior for exact terms | Semantic/paraphrase dialogue retrieval, scene search, or actor performance | Engineering A; Babel/LDC data gated |
| Spoken/visual archive | [SAVA, MediaEval 2015](https://ceur-ws.org/Vol-1436/Paper11.pdf) | Spoken-plus-visual query to unrestricted BBC archive intervals | Whether combined evidence retrieves useful broadcast segments | Actor clustering or reproducibility on presently obtainable public media | Blocked/reference-only |
| Multilingual temporal | [mTVR](https://aclanthology.org/2021.acl-short.92/) | English/Chinese multilingual TV moment retrieval | Whether a multilingual retrieval stack preserves temporal retrieval across those two languages | Urdu support, current MiniLM multilingual quality, or actor clustering | Reference; not an intentional current claim |
| Visual moment | [DiDeMo](https://github.com/LisaAnne/LocalizingMoments) | Natural-language query to one of 21 fixed moments in a known video | Whether CLIP frame scores and deterministic five-second aggregation rank the human-selected moment | Corpus-wide search, variable boundary quality, dialogue, or actors | Engineering A; ready |
| Visual moment/highlight | [QVHighlights](https://github.com/jayleicn/moment_detr) | Query to ranked variable-duration moments and dense two-second highlight saliency | Whether zero-shot visual similarity finds relevant intervals and assigns useful temporal saliency | Dialogue or actor performance; parity with supervised temporal models | Engineering A; storage/compute gated |
| Visual moment | [Charades-STA](https://github.com/jiyanggao/TALL) | Query to ranked intervals in short indoor activity videos | Whether fixed-grid CLIP scoring localizes described actions in short videos | Corpus search, speech, actors, or broad-domain generalization | Engineering A; data agreement gated |
| Whole-video visual | [MSR-VTT](https://www.microsoft.com/en-us/research/publication/msr-vtt-a-large-video-description-dataset-for-bridging-video-and-language/) | Text-to-whole-video ranking | Whether pooled VidXP scene embeddings retrieve the correct short video from a corpus | Timestamp localization, dialogue retrieval, or actors | Engineering A; media preparation required |
| Visual moment | [ActivityNet Captions](https://cs.stanford.edu/people/ranjaykrishna/densevid/) | Natural-language grounding and dense event descriptions in longer activity videos | Whether scene retrieval generalizes beyond short fixed-grid videos to longer event intervals | Dialogue, actors, or robustness to current YouTube attrition | Engineering A; preparation/split risk |
| Long-film moment | [MAD](https://github.com/Soldelli/MAD) | Audio-description query to intervals across long movies | Whether VidXP can search and localize descriptions at movie scale | In-scene dialogue, actor clustering, or a run without separately obtained movies | Engineering A; NDA/media blocked |
| Egocentric moment | [Ego4D NLQ](https://ego4d-data.org/docs/benchmarks/episodic-memory/) | Natural-language episodic-memory query to an egocentric video interval | Whether scene retrieval works over long first-person activities and sparse targets | Entertainment-video dialogue, actor identity, or low-cost deployment | Engineering A; access and approximately 1 TB cost gated |
| Fine-grained robustness | [VERIFIED](https://github.com/hlchen23/VERIFIED) | Moment retrieval against subtly different static/dynamic hard negatives | Whether VidXP distinguishes fine-grained objects, states, and actions rather than exploiting coarse dataset cues | Dialogue, actors, or a fully reproducible result until its evaluator/license issues are resolved | Artifact/license blocked |
| Long-video visual | [LoVR](https://github.com/TechNomad-ds/LoVR-benchmark) | Text-to-clip/video retrieval in long videos | Whether CLIP-style retrieval survives longer context and more distractor clips | Dialogue, actors, or reliable publication evidence with the current inconsistent evaluator | Technically A; evaluator currently unreliable |
| Face clustering | [BCL on BBT/Buffy](https://github.com/makarandtapaswi/BallClustering_ICCV2019) | Unknown-number clustering of labelled face tracks, measured with WCP/NMI and cluster count | Whether VidXP keeps the same character together without merging different characters | Face-detection recall when benchmark tracks are supplied, scene/dialogue retrieval, or VidXP embeddings if only BCL's features are used | Engineering A/medium; raw episode media gated |
| Constrained face clustering | [C1C / Friends](https://github.com/vkalogeiton/c1c) | Face-track clustering using temporal cannot-link relations across TV episodes | Whether temporal constraints reduce false actor merges and fragmentation | End-to-end face detection or reproduction of the unpublished C1C algorithm | Data adaptable; algorithm code unavailable |
| Multimodal person clustering | [VPCD](https://www.robots.ox.ac.uk/~vgg/data/Video_Person_Clustering/) | Person clustering from face, body, and voice tracks | How much multimodal identity evidence can improve clustering over face-only features | Current VidXP performance as a face-only system, unless evaluated on a declared face-only slice | Feature-level adaptable; implementation incomplete |
| End-to-end movie actors | [Hannah](https://www.interdigital.com/data_sets/hannah-dataset) | Face detection, tracking, and identity grouping throughout one full movie | Whether VidXP finds faces, maintains actor identity over time, and avoids false merges/fragmentation end to end | Generalization across many movies or dialogue/scene retrieval | Engineering A/medium; agreement and movie gated |
| Movie components | [MovieNet](https://movienet.github.io/) | Character, scene, subtitle, and metadata tasks at movie scale | Component-level character or scene performance and possible cross-component analyses | One official end-to-end VidXP score or raw-movie performance when movies are excluded | Registration/storage gated; component source |
| Face clustering | [IJB-B](https://openaccess.thecvf.com/content_cvpr_2017_workshops/w6/html/Whitelam_IARPA_Janus_Benchmark-B_CVPR_2017_paper.html) | Template/face clustering with B-cubed precision, recall, and F-score | Whether embeddings separate identities under the IJB protocol | Within-video actor continuity, dialogue/scene search, or a new run without an existing lawful copy | Distribution discontinued; reference-only |
| Movie face clustering | [MovieFaceCluster / VideoClusterNet](https://www.ecva.net/papers/eccv_2024/papers_ECCV/html/4432_ECCV_2024_paper.php) | Unsupervised face-track clustering across nine movies | Whether VidXP actor clustering generalizes to a recent movie protocol | Executable evidence while the dataset link and code remain unavailable | Blocked/reference-only |
| Egocentric face clustering | [EasyCom-Clustering](https://github.com/ibug-group/Easycom-Clustering) | Face-track clustering in egocentric social video | Whether actor clusters remain stable under first-person views, occlusion, and viewpoint changes | Any executable result until the promised data is released | Blocked/reference-only |
| Face verification provenance | [LFW / dlib protocol](https://github.com/ageitgey/face_recognition) | Same/different identity verification on still-image pairs | Only the provenance and generic discrimination of the underlying face embedding | VidXP actor clustering, face detection coverage, temporal continuity, or unknown-K performance | Not an actor benchmark; provenance only |
| Combined temporal | [LongVALE](https://github.com/ttgeng233/LongVALE) | Vision, speech, and generic-audio event grounding in long videos | Whether fixed fusion of VidXP scene and speech evidence localizes multimodal events | Actor clustering or full omni-modal coverage because VidXP lacks generic-audio recognition | Engineering A/medium; media/runtime gated |
| Audiovisual retrieval | [FLARE](https://flarebench.github.io/) | Visual-only, audio-only, and joint text-to-clip/video retrieval | Where VidXP's scene, speech, and fixed-fusion rankings succeed or fail across evidence types | Actor performance, human-authored-query generalization, or generic sound capability | Engineering A/medium; ready/watchlist preprint |
| Large-corpus event | [MultiVENT 2.0](https://huggingface.co/datasets/hltcoe/MultiVENT2.0) | Multilingual event-centric ranked-video retrieval using visual, audio, OCR, ASR, and metadata evidence | Whether existing VidXP visual, speech, and metadata paths scale to a large heterogeneous corpus; unsupported channels become measurable weaknesses | Timestamp localization, actor clustering, full OCR/audio coverage, or multilingual adequacy of current MiniLM | Engineering A with large operational adapter; approximately 1.93 TB gated |
| Large-corpus shot | [TRECVID AVS / V3C](https://www-nlpir.nist.gov/projects/tv2025/avs.html) | Natural-language query to ranked master shots, measured with xinfAP | Whether VidXP scene retrieval scales to over a million judged shots and returns useful corpus rankings | Dialogue or actor performance, or comparable latency across different hardware | Engineering A/medium; agreement and approximately 1.6 TB gated |
| Multimodal whole-video | [MUVR](https://github.com/debby-0527/MUVR) | Text, video, and mixed query to ranked untrimmed videos | Whether VidXP ranks relevant videos for the declared text or reusable-CLIP query slices | Timestamp localization, dialogue understanding, actors, or unsupported QA/reasoning tracks | Text/base slice adaptable; lower priority |
| Vector database | [VectorDBBench](https://github.com/zilliztech/vectordbbench) | ANN index build time, recall, latency, and throughput | Whether Chroma retrieves VidXP embeddings accurately and efficiently at a stated scale | Video decoding/model cost or end-to-end retrieval quality | Engineering A; ready diagnostic |
| ASR/alignment component | [WhisperX evaluation](https://www.isca-archive.org/interspeech_2023/bain23_interspeech.html) | Transcription error and word-timestamp alignment accuracy | Whether the configured WhisperX path reproduces component-level transcription/timing behavior on a matching speech set | Semantic dialogue retrieval or video search quality | Component reference; separate evaluation needed |
| Broadcast speech component | [MGB Challenge](https://www.cstr.ed.ac.uk/downloads/publications/2015/bell15_mgb_challenge.pdf) | Broadcast ASR, diarization, and subtitle alignment | How transcription/alignment behaves on difficult broadcast audio if that component is run | Scene retrieval, actor clustering, or current end-to-end VidXP quality | Component reference; not selected |

### Related systems are not benchmark protocols

These systems can guide architecture or become same-harness external baselines, but
their published numbers alone do not answer a VidXP capability question:

| System | What a same-harness run could tell us | Why the published work alone is insufficient |
| --- | --- | --- |
| [WISE](https://www.robots.ox.ac.uk/~vgg/publications/2026/sridhar2026wise/) | Whether a broader released multimodal engine outperforms VidXP on the exact selected corpus/evaluator/hardware | The paper provides deployments and timing context, not a portable judged benchmark |
| [MVSE](https://doi.org/10.1049/cvi2.12303) | How face/scene/speaker/ASR fusion and approximate search compare if its full system and judgments were obtainable | BBC corpus, relevance data, and implementation are not portable |
| [ContextIQ](https://openaccess.thecvf.com/content/WACV2025/html/Chaubey_ContextIQ_A_Multimodal_Expert-Based_Video_Retrieval_System_for_Contextual_Advertising_WACV_2025_paper.html) | Whole-video comparison of video/audio/transcript/metadata experts on a shared dataset | No public implementation/checkpoint; its custom result is not the VidXP task |
| [Collaborative Experts](https://www.robots.ox.ac.uk/~vgg/research/collaborative-experts/) | A supervised multi-expert whole-video baseline on MSR-VTT or another shared retrieval set | It does not natively evaluate timestamps or actor clustering |

## Ranked execution candidates

| Priority | Lane | Benchmark | Engineering | Operations | Main constraint |
| --- | --- | --- | --- | --- | --- |
| 1 | Visual | DiDeMo | A, small adapter | Ready | Published five-second candidate aggregation |
| 2 | Dialogue | HiREST released-ASR mode | A, small adapter | Ready | Queries are instructional goals rather than quoted dialogue |
| 3 | Visual | QVHighlights | A, medium adapter | Gated | 133.9 GiB raw archive and current CPU indexing cost |
| 4 | Dialogue | QuerYD transcript/proposal mode | A, small/medium adapter | Ready; raw narration pending | Narration rather than in-scene dialogue |
| 5 | Dialogue | TVR, `t` subset | A, medium adapter | Gated | Lawful TV clips with original audio |
| 6 | Actor | BCL on BBT/Buffy | A, medium evaluator adapter | Gated | Lawful raw episodes needed for VidXP embeddings |
| 7 | Visual | Charades-STA | A, medium adapter | Gated | Dataset agreement and narrow staged domain |
| 8 | Whole system | LongVALE | A, medium fixed-fusion adapter | Gated | About 254 GB, raw-media survival, no generic-audio capability |
| 9 | Whole system | FLARE | A, medium adapter | Ready/watchlist | Preprint; generated rank-filtered queries; generic audio unsupported |
| 10 | Actor | Hannah | A, medium evaluator adapter | Gated | Research agreement and separately obtained movie |
| 11 | Actor/system | MovieNet | A for component slices | Gated | Registration; movies excluded; actor labels are keyframe-oriented |

## Common adapter contract

Before benchmark-specific work, VidXP needs one small prediction contract:

```text
query_id -> [
  {video_id, start, end, score},
  ...
]
```

It must support stable corpus-wide video IDs, top-k ranked results, similarity
scores, and non-zero intervals. This is shared benchmark plumbing, not a generic
evaluation framework.

The scene-only slice is roughly one to two developer days. A reusable dialogue and
scene contract with batching, namespaces, filters, tests, and serializers is roughly
three to five developer days, excluding dataset downloads and indexing.

Actor evaluation needs a separate minimal contract:

```text
video_id -> [
  {face_or_track_id, predicted_cluster_id, optional_bbox, optional_time},
  ...
]
```

The evaluator, not VidXP, should compute the published metrics.

## Dialogue and speech-backed temporal retrieval

### TVR / XML

- **Sources:** [paper](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123660443.pdf),
  [official repository](https://github.com/jayleicn/TVRetrieval),
  [standalone evaluator](https://github.com/jayleicn/TVRetrieval/tree/master/standalone_eval).
- **Year/venue:** 2020, ECCV.
- **Task:** corpus-wide video moment retrieval (VCMR), single-video moment
  retrieval (SVMR), and video retrieval (VR).
- **Inputs/output:** natural-language query plus TV clips and subtitles; ranked
  `[video_id, start, end, score]` predictions.
- **Scale:** 109K queries over 21.8K clips from six English TV shows, approximately
  460 hours. Queries are labelled `t` for subtitle-related, `v` for visual, or `vt`
  for joint evidence.
- **Metrics:** Recall@1/5/10/100 at temporal IoU 0.5 and 0.7.
- **Artifacts:** public annotations, features, XML/CAL/ExCL/MEE baselines, and MIT
  code. Raw TV footage remains copyrighted; availability of original audio is the
  decisive feasibility question.
- **VidXP fit:** `t` is the strongest published dialogue-aligned slice and `v`
  provides a related visual slice. VidXP must emit ranked intervals and stable
  video IDs. A subtitle-only run would test MiniLM retrieval but not WhisperX.
- **Verdict/confidence:** **Adaptable if media is secured; confirmed protocol,
  unresolved raw-media access.**

### HiREST

- **Sources:** [paper](https://openaccess.thecvf.com/content/CVPR2023/papers/Zala_Hierarchical_Video-Moment_Retrieval_and_Step-Captioning_CVPR_2023_paper.pdf),
  [official repository](https://github.com/j-min/HiREST),
  [feature instructions](https://github.com/j-min/HiREST/tree/main/extraction/video_features).
- **Year/venue:** 2023, CVPR.
- **Task:** hierarchical query-to-video retrieval followed by moment localization,
  segmentation, and step captioning.
- **Scale:** about 3.4K text-video pairs; roughly 1.1K relevant videos with moment
  and step annotations. Test retrieval includes 1,391 candidates plus 2,891
  negatives.
- **Metrics:** video R@1/5/10/50; moment R@1 at tIoU 0.5 and 0.7.
- **Artifacts:** MIT code, evaluator, pretrained model, ASR, MiniLM ASR embeddings,
  and visual features. Raw video is recovered from YouTube.
- **VidXP fit:** unusually strong implementation match: the official baseline uses
  Whisper transcripts and `all-MiniLM-L6-v2`. The queries express procedural goals,
  not dialogue quotations.
- **Verdict/confidence:** **Engineering A and ready in released-ASR mode.** This can
  run VidXP's own chunking, MiniLM embedding, Chroma indexing, ranking, and official
  evaluation now. A raw-video WhisperX run remains subject to a full YouTube
  survival audit.

### QuerYD

- **Sources:** [paper](https://www.robots.ox.ac.uk/~vgg/publications/2021/Oncescu21/oncescu21.pdf),
  [dataset](https://www.robots.ox.ac.uk/~vgg/data/queryd/),
  [downloader](https://github.com/oncescuandreea/QuerYD_downloader),
  [retrieval code](https://github.com/albanie/collaborative-experts).
- **Year/venue:** 2021, ICASSP.
- **Task:** video retrieval and localization from natural-language descriptions.
- **Scale:** 2,593 YouTube videos, 207 hours of video, 74 hours of volunteer audio
  descriptions, and 31,441 descriptions; 13,019 have start/end intervals.
- **Metrics:** R@1/5/10, median rank, and mean rank.
- **Artifacts:** video URLs, description audio, transcripts, timestamps, splits,
  precomputed features, and baseline code. A clear dataset-wide license was not
  found; YouTube media has separate rights.
- **VidXP fit:** can exercise WhisperX, word timing, MiniLM, indexing, and
  timestamp retrieval. The speech is narration rather than in-scene dialogue, and
  the published localization baseline ranks oracle proposals rather than freely
  predicting boundaries.
- **Verdict/confidence:** **Engineering A and ready for the released
  transcript/proposal protocol.** End-to-end WhisperX over narrator WAV files and
  the exact reuse license remain unresolved.

### TVR-Ranking

- **Sources:** [paper](https://arxiv.org/abs/2407.06597),
  [official release](https://huggingface.co/axgroup/TVR-Ranking).
- **Year/venue:** 2025, SIGIR-AP.
- **Task:** imprecise query to a graded ranked list of corpus moments.
- **Scale:** 94,442 manually judged query-moment pairs with five relevance levels.
- **Metrics:** IoU-aware nDCG at ranked cutoffs and overlap thresholds.
- **Artifacts:** annotations and current baseline code; raw video is inherited from
  TVR. The visible documentation says Creative Commons without naming the variant.
- **VidXP fit:** excellent search-product evaluation definition once corpus-ranked
  interval output exists.
- **Verdict/confidence:** **Adaptable; confirmed protocol, unresolved media and
  exact license.**

### TREC Podcasts and NIST OpenKWS

- [TREC Podcasts](https://trecpodcasts.github.io/) evaluates ranked, timestamped
  spoken-content segments with graded relevance and nDCG. It is an excellent
  protocol reference, but organizers stopped granting corpus access in December
  2023. **Reference-only now.**
- [NIST OpenKWS](https://www.nist.gov/document/openkws13-evalplan-v4pdf) evaluates
  all occurrences of a text term in unsegmented speech using ATWV, temporal
  matching, thresholds, indexing time, and search time. Babel/LDC licensing and
  the exact-keyword task make it a conditional component benchmark rather than the
  primary semantic retrieval test. **Adaptable only with licensed data.**

## Visual scene and temporal retrieval

### DiDeMo

- **Sources:** [paper](https://arxiv.org/abs/1708.01641),
  [official repository and data](https://github.com/LisaAnne/LocalizingMoments),
  [official evaluator](https://github.com/LisaAnne/LocalizingMoments/blob/master/utils/eval.py).
- **Year/venue:** 2017, ICCV.
- **Task:** natural-language query to a ranked set of moments in a known video.
- **Scale verified from official JSON:** 33,005 train annotations/8,511 videos;
  4,180 validation/1,094; 4,021 test/1,037.
- **Output/metrics:** rank the 21 contiguous moments formed from six five-second
  chunks; Rank@1, Rank@5, and mean IoU with multiple human annotations.
- **Artifacts/license:** downloadable YFCC100M/Flickr videos with individual
  Creative Commons records; BSD-2-Clause code and evaluator.
- **VidXP fit:** aggregate CLIP frame similarity per five-second chunk, construct
  the legal moments, and rank them. No training is required.
- **Verdict/confidence:** **Adaptable; confirmed and first execution candidate.**

### QVHighlights / Moment-DETR

- **Sources:** [paper](https://proceedings.neurips.cc/paper/2021/hash/62e0973455fd26eb03e91d5741a4a3bb-Abstract.html),
  [official repository](https://github.com/jayleicn/moment_detr),
  [data details](https://github.com/jayleicn/moment_detr/blob/main/data/README.md).
- **Year/venue:** 2021, NeurIPS.
- **Task:** ranked moment retrieval plus highlight saliency for two-second clips.
- **Scale:** 7,218 training, 1,550 validation, and 1,542 public test-with-ground-
  truth annotation rows.
- **Metrics:** moment mAP over tIoU 0.50:0.05:0.95, mAP@0.5/0.75, R@1 at tIoU
  0.5/0.7, highlight mAP, and Hit@1.
- **Artifacts/license:** official evaluator, checkpoints, and an 8 GB
  pre-extracted-feature release; raw archive verified at 143,734,787,897 bytes
  (133.9 GiB). Code is MIT; annotations are CC BY-NC-SA 4.0.
- **VidXP fit:** aggregate frames into two-second clips and construct scored,
  non-zero intervals. Highlight metrics may be omitted unless VidXP is explicitly
  adapted to produce dense saliency.
- **Verdict/confidence:** **Adaptable; confirmed and recommended primary visual
  benchmark.**

### Charades-STA

- **Sources:** [TALL paper/repository](https://github.com/jiyanggao/TALL),
  [Charades dataset](https://prior.allenai.org/projects/charades),
  [data agreement](https://prior.allenai.org/projects/data/charades/license.txt).
- **Year/venue:** 2017, ICCV.
- **Task:** query to a start/end interval in a known short video.
- **Scale:** 13,898 training and 4,233 test sentence-interval pairs over the
  9,848-video Charades collection.
- **Metrics:** R@1/R@5 at tIoU 0.5 and 0.7.
- **Artifacts/license:** scaled video is about 13 GB; academic, non-profit, or
  government research agreement.
- **VidXP fit:** manageable secondary benchmark after a sliding/proposal-window
  adapter; domain is staged indoor actions.
- **Verdict/confidence:** **Adaptable; confirmed.**

### Larger or weaker visual options

| Benchmark | Finding | Verdict |
| --- | --- | --- |
| [MSR-VTT](https://www.microsoft.com/en-us/research/publication/msr-vtt-a-large-video-description-dataset-for-bridging-video-and-language/) | Useful corpus/video-ranking sanity check, but no timestamp localization | Adaptable component |
| [MAD](https://github.com/Soldelli/MAD) | 384K descriptions over 650 movies and 1,200+ hours; raw movies require separate acquisition and an NDA | Reference-only at present |
| [Ego4D NLQ](https://ego4d-data.org/docs/benchmarks/episodic-memory/) | Strong long-video localization, but authorization plus roughly 1 TB clips or 220 GB features | Adaptable, deferred on cost |
| [VERIFIED](https://github.com/hlchen23/VERIFIED) | Valuable hard-negative variants; incomplete evaluator and no explicit repository license found | Partially confirmed, deferred |
| [LoVR](https://github.com/TechNomad-ds/LoVR-benchmark) | Attractive long-video CLIP benchmark, but repository evaluator paths and released split sizes are inconsistent | Reference-only until repaired |
| [ActivityNet Captions](https://cs.stanford.edu/people/ranjaykrishna/densevid/) | Established but affected by YouTube attrition, split variants, and larger preparation cost | Adaptable, later extension |

## Actor and video-face clustering

### BCL on BBT and Buffy

- **Sources:** [ICCV paper](https://openaccess.thecvf.com/content_ICCV_2019/html/Tapaswi_Video_Face_Clustering_With_Unknown_Number_of_Clusters_ICCV_2019_paper.html),
  [official repository](https://github.com/makarandtapaswi/BallClustering_ICCV2019).
- **Year/venue:** 2019, ICCV.
- **Task:** cluster face tracks in a video when the number of identities is unknown.
- **Dataset/protocol:** six episodes from *The Big Bang Theory* season 1 and six
  from *Buffy the Vampire Slayer* season 5; report all-character and
  background-character evaluations.
- **Metrics:** weighted clustering purity (WCP), normalized mutual information
  (NMI), and predicted number of clusters.
- **Artifacts:** official evaluator, pretrained checkpoint, track metadata, HAC
  baseline, and 256-D SE-ResNet50 features. The track and feature archives were
  confirmed reachable at about 5.5 MB and 543 MB. No clear repository license was
  found; raw copyrighted episodes are not included.
- **VidXP fit:** the closest reproducible unknown-K actor-clustering protocol.
  Supplied features cannot validate VidXP's dlib 128-D embeddings. A true VidXP run
  needs lawful raw episodes or derived face crops plus an adapter from per-frame
  detections to the benchmark tracks.
- **Verdict/confidence:** **Engineering A/medium, operations gated.** Stable
  per-detection cluster output plus frozen time/bounding-box matching is sufficient
  for the official evaluator. Raw-media and code-license constraints remain.

### VPCD

- **Sources:** [paper](https://openaccess.thecvf.com/content/ICCV2021W/CVEU/html/Brown_Face_Body_Voice_Video_Person-Clustering_With_Multiple_Modalities_ICCVW_2021_paper.html),
  [project page](https://www.robots.ox.ac.uk/~vgg/data/Video_Person_Clustering/),
  [repository](https://github.com/Andrew-Brown1/Video_Person_Clustering).
- **Year/venue:** 2021, ICCV Workshop.
- **Task:** person clustering using face, body, and voice tracks.
- **Scale:** 23+ hours across six programme sets, approximately 35K face, 39K body,
  and 27K voice tracks representing 300+ characters.
- **Metrics:** WCP, NMI, and predicted cluster count.
- **Artifacts:** 5.69 GB archive verified reachable; project states CC BY 4.0 for
  the dataset while original videos retain owner copyright. The repository still
  says code is forthcoming, and warns that released-data statistics differ from
  the paper.
- **VidXP fit:** useful multi-modal system reference and labelled feature source,
  but VidXP presently clusters faces only.
- **Verdict/confidence:** **Adaptable as a feature-level component/reference;
  confirmed artifact, incomplete reproduction package.**

### C1C / Friends face clustering

- **Sources:** [project](https://www.robots.ox.ac.uk/~vgg/research/c1c/),
  [BMVC paper](https://www.bmvc2020-conference.com/assets/papers/0899.pdf),
  [repository](https://github.com/vkalogeiton/c1c).
- **Year/venue:** 2020, BMVC.
- **Task:** face-track clustering with cannot-link temporal constraints.
- **Dataset:** BBT, Buffy, Sherlock, and the introduced Friends protocol.
- **Artifacts:** track/features/parser releases are present and the Friends feature
  archive was confirmed reachable at about 1.67 GB. The algorithm repository still
  says code is forthcoming; raw TV video is not included.
- **Verdict/confidence:** **Adaptable data/reference; confirmed data, unavailable
  algorithm code.**

### Hannah

- **Source:** [official dataset page](https://www.interdigital.com/data_sets/hannah-dataset).
- **Task/data:** full-movie face boxes, tracks, identities, and speech segments for
  *Hannah and Her Sisters*: 153,833 frames, 245 shots, 202,178 face boxes, 2,002
  face tracks, 1,518 speech segments, and 254 labels.
- **Access:** research-only agreement by email; annotations cannot be redistributed
  and the movie must be obtained separately.
- **VidXP fit:** the closest labelled route for end-to-end actor detection,
  clustering, and missed-face analysis, rather than clustering supplied features.
- **Verdict/confidence:** **Adaptable but gated; confirmed.** Do not request access
  without explicit user authorization.

### Other actor datasets

| Benchmark | Finding | Verdict |
| --- | --- | --- |
| [MovieNet](https://movienet.github.io/) | 1,100 movies with character boxes/IDs, scenes, subtitles, and metadata; registration required, keyframes are 161 GB, movies excluded | Adaptable component source |
| [IJB-B](https://openaccess.thecvf.com/content_cvpr_2017_workshops/w6/html/Whitelam_IARPA_Janus_Benchmark-B_CVPR_2017_paper.html) | Has a formal B-cubed face-clustering protocol, but NIST discontinued distribution in March 2023 | Reference-only unless already held |
| [MovieFaceCluster / VideoClusterNet](https://www.ecva.net/papers/eccv_2024/papers_ECCV/html/4432_ECCV_2024_paper.php) | Relevant nine-movie protocol; paper's dataset URL currently returns 404 and no code was found | Reference-only |
| [EasyCom-Clustering](https://github.com/ibug-group/Easycom-Clustering) | 94,047 face tracks in egocentric video claimed; repository still promises a future download and has no release | Reference-only |

## Whole-system and efficiency evaluation

### LongVALE

- **Sources:** [CVPR paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Geng_LongVALE_Vision-Audio-Language-Event_Benchmark_Towards_Time-Aware_Omni-Modal_Perception_of_Long_Videos_CVPR_2025_paper.pdf),
  [official repository](https://github.com/ttgeng233/LongVALE),
  [dataset](https://huggingface.co/datasets/ttgeng233/LongVALE).
- **Year/venue:** 2025, CVPR.
- **Task:** vision–audio–language event understanding, including omni-modal
  temporal grounding with `[start, end]` output, dense captioning, and segment
  captioning.
- **Scale:** 8,411 videos, 549 hours, and 105,730 non-overlapping events. The
  human-refined evaluation split contains 1,171 videos, 13,867 events, and 75.6
  hours.
- **Metrics:** R@1 at tIoU 0.3/0.5/0.7 and mean IoU for temporal grounding.
- **Artifacts/license:** public annotations, training/evaluation code, model code,
  and released CLIP ViT-L/14, BEATs, and Whisper large-v2 features. The repository
  is MIT; the dataset card is CC BY-NC-SA 4.0 and reports about 254 GB. Underlying
  video copyright remains with source owners.
- **VidXP fit:** strongest peer-reviewed combined temporal target. It covers vision,
  speech, and generic audio but not actors. VidXP can produce ranked intervals and
  combine its existing visual and speech lists with a frozen, non-learned fusion
  rule. Generic-audio queries remain an unsupported capability and may score
  poorly. Released features can reproduce external baselines but cannot substitute
  for running VidXP on raw video.
- **Verdict/confidence:** **Adaptable and evaluator-executable after a fixed
  visual/speech fusion adapter; confirmed.** Generic-audio coverage remains an
  explicit limitation.

### FLARE

- **Sources:** [project](https://flarebench.github.io/),
  [code](https://github.com/YqjMartin/FLARE),
  [dataset](https://huggingface.co/datasets/YqjMartin/FLARE),
  [preprint](https://arxiv.org/abs/2605.10228).
- **Status:** 2026 arXiv preprint under anonymous review as verified on the project
  page.
- **Task/scale:** text-to-video and text-to-clip retrieval over 399 long videos,
  225.4 hours, 87,697 clips, and 274,933 visual-only, audio-only, and hard joint
  audio-visual queries.
- **Metrics:** R@1/5/10.
- **Artifacts/license:** 71.2 GB public segmented MP4 release with audio; MIT code;
  stated CC BY 4.0 dataset; harness for 15 retrievers.
- **VidXP fit:** closest obtainable combined scene/dialogue retrieval stress test.
  It does not test actor clustering. Audio queries include music and sound events,
  so a declared speech-only subset is necessary for VidXP's dialogue path.
- **Caveat:** generated queries were retained using a rank-1 embedding filter, which
  creates selection bias.
- **Verdict/confidence:** **Adaptable watchlist; artifacts confirmed, publication
  status immature.**

### MultiVENT 2.0

- **Sources:** [CVPR paper](https://openaccess.thecvf.com/content/CVPR2025/papers/Kriz_MultiVENT_2.0_A_Massive_Multilingual_Benchmark_for_Event-Centric_Video_Retrieval_CVPR_2025_paper.pdf),
  [official downloads](https://nlp.jhu.edu/multivent/download.html),
  [dataset and evaluator](https://huggingface.co/datasets/hltcoe/MultiVENT2.0).
- **Year/venue:** 2025, CVPR.
- **Task/scale:** ranked event/news video retrieval over more than 218,000 videos,
  3,906 manually written queries, and 16,116 relevance judgments. Queries can
  require visual, audio, OCR, ASR, or metadata evidence.
- **Languages/output/metric:** Arabic, Chinese, English, Korean, Russian, and
  Spanish; ranked video IDs; principal metric nDCG@10.
- **Artifacts/license/cost:** public evaluator, judgments, videos/audio, and
  example baseline runs. The dataset card states Apache-2.0. Verified repository
  storage is approximately 1.93 TB.
- **VidXP fit:** strong large-corpus stress test, but it needs video aggregation,
  corpus-safe IDs, top-k, and modality fusion. VidXP lacks OCR, metadata, and
  generic-audio retrieval, and MultiVENT has no timestamp or actor task.
- **Verdict/confidence:** **Adaptable at high cost; confirmed.** Multilingual scope
  comes from this benchmark, not from an assumed VidXP language requirement.

### TRECVID AVS / V3C

- **Sources:** [official AVS task](https://www-nlpir.nist.gov/projects/tv2025/avs.html),
  [official data page](https://www-nlpir.nist.gov/projects/tv2025/data.html),
  [2024 overview](https://trec.nist.gov/pubs/trec33/papers/Overview_avs_vtt_actev.pdf).
- **Task:** sentence query to a ranked list of up to 1,000 master-shot IDs.
- **Scale:** V3C2 contains 9,760 videos, approximately 1,300 hours and 1,425,454
  segments at about 1.6 TB. Full V3C is substantially larger.
- **Metrics:** mean xinfAP; runs also report wall-clock seconds per query.
- **Access/fit:** past queries, judgments, and evaluation tools are available;
  current-year participation requires agreements. VidXP could map a scene point to
  a master shot but must return a corpus ranking. This tests visual retrieval only.
- **Verdict/confidence:** **Adaptable at very high cost; confirmed, deferred.**

### MUVR

- **Sources:** [NeurIPS page](https://papers.neurips.cc/paper_files/paper/2025/hash/2a80c10b1fd6a6488a96cc1f4fbacc84-Abstract-Datasets_and_Benchmarks_Track.html),
  [repository](https://github.com/debby-0527/MUVR),
  [dataset](https://huggingface.co/datasets/debby0527/MUVR).
- **Year/venue:** 2025, NeurIPS Datasets & Benchmarks.
- **Task/scale:** ranked-video retrieval over approximately 53K untrimmed videos,
  1,050 text/video/mixed queries, and about 84K matches.
- **Artifacts:** public roughly 100 GB CC BY 4.0 dataset and evaluator support; an
  explicit code license was not visible during verification.
- **VidXP fit:** only the text-query subset is close to current scene search. There
  is no timestamp, transcript, or actor objective.
- **Verdict/confidence:** **Adaptable but lower fit; partially confirmed license.**

### Closest system papers without portable benchmarks

| System | Overlap with VidXP | Why it is reference-only |
| --- | --- | --- |
| [MVSE](https://doi.org/10.1049/cvi2.12303) | Face, scene, speaker, and ASR processing; multi-modal fusion; ranked BBC archive videos | Its BBC corpus, queries, and relevance data are not released as a reusable benchmark; no public implementation was verified |
| [WISE](https://www.robots.ox.ac.uk/~vgg/publications/2026/sridhar2026wise/) | Scene/object/face, acoustic-event, WhisperX speech, metadata, composite search; current [Apache-2.0 code](https://gitlab.com/vgg/wise/wise) | SIGIR 2026 system/demo paper with deployments and timing claims, not a portable judged relevance protocol; face mode is identity search, not clustering |
| [ContextIQ](https://openaccess.thecvf.com/content/WACV2025/html/Chaubey_ContextIQ_A_Multimodal_Expert-Based_Video_Retrieval_System_for_Contextual_Advertising_WACV_2025_paper.html) | Video, audio, transcript, and metadata experts | Whole-clip retrieval; only supplemental annotations are public, with no implementation/checkpoint |
| [Collaborative Experts](https://www.robots.ox.ac.uk/~vgg/research/collaborative-experts/) | Appearance, motion, scene, ASR, OCR, and audio expert streams | Strong whole-video architecture/baseline reference but no actor or native moment output |
| [SAVA, MediaEval 2015](https://ceur-ws.org/Vol-1436/Paper11.pdf) | Queries contain spoken- and visual-content fields and retrieve intervals from about 4,021 hours of BBC archive video | Historically close protocol, but participant-provided BBC material and the old evaluation package are not verified as presently obtainable |

### Engineering measurements

Published indexing and latency numbers are not comparable unless data, hardware,
preprocessing, cache state, concurrency, and timing boundaries match. VidXP should
still report a reproducible local protocol:

- fixed video-duration buckets and corpus sizes;
- wall-clock indexing time separately for audio, visual, and face paths;
- real-time factor and videos/hour;
- peak host RAM, accelerator memory where used, and index size on disk;
- cold and warm p50/p95 query latency at top-k;
- hardware, model versions, thread counts, batch sizes, and cache policy;
- failures and media excluded from denominators.

These are system measurements, not a substitute for retrieval accuracy.

[VectorDBBench](https://github.com/zilliztech/vectordbbench) can separately measure
Chroma index build time, recall, latency, and maximum QPS using custom embeddings.
It should be labelled a database-only diagnostic: it excludes video decoding,
model inference, media preprocessing, and end-user latency.

## Rejected scope expansions

- Urdu or multilingual evaluation is not required by the current product claim.
  mTVR, VATEX, and multilingual speech corpora remain references only unless
  multilingual retrieval becomes intentional.
- Face verification datasets such as LFW do not evaluate within-video actor
  clustering and cannot serve as the actor benchmark.
- Speaker diarization and face/body/voice fusion are not implemented capabilities.
  They may appear as future-work comparisons, not current benchmarks.

## Feasibility checks alongside adapter work

1. Confirm legal and technical access to TVR clips with original audio.
2. Probe a stratified sample of HiREST and QuerYD YouTube IDs for survival.
3. Resolve the QuerYD and TVR-Ranking annotation license language.
4. Confirm DiDeMo media retrieval for a small test sample and preserve each source
   item's Creative Commons record.
5. Decide whether the QVHighlights 133.9 GiB raw download is acceptable or whether
   a smaller validation sample is the first milestone.
6. Estimate the LongVALE raw-video survival rate and storage/processing budget
   before treating it as an executable combined benchmark.
7. Determine whether the team owns or can lawfully access BBT/Buffy episodes for an
   end-to-end BCL run; otherwise separate a feature-level clustering experiment
   from a true VidXP actor result.
8. Do not contact Hannah custodians or accept research agreements without explicit
   user authorization.
9. Freeze benchmark versions, splits, evaluator commits, and checksums before
   reporting any result.

## Proposed execution order after review

1. Implement the shared stable-ID, top-k, score, interval, filter, and serializer
   contract with tests.
2. Run DiDeMo on a small verified sample and HiREST's released-ASR protocol in
   parallel, then run their full public evaluation paths.
3. Run QuerYD's transcript/proposal protocol while probing narrator-audio access.
4. Run QVHighlights validation, first on a declared subset and then in full if
   storage permits.
5. Resolve TVR media access. If successful, run `t`, `v`, and `vt` separately.
6. Run BCL's official evaluator first on its supplied reference features to verify
   the protocol, then on VidXP-derived features only if lawful raw media is
   available.
7. Add fixed hardware-aware indexing and query measurements to every executed
   experiment.
8. Run LongVALE after freezing a simple visual/speech rank-fusion rule and
   confirming its media/runtime budget.
9. Consider Charades-STA, FLARE, and large-corpus MultiVENT/TRECVID experiments
   only after the core suite produces valid, archived predictions.
