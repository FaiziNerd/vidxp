# Relevant research-paper inventory

Collection index: [Benchmarking research](README.md)

Status: Active review queue

Last verified: 2026-07-25

Related decision record: [Published benchmark catalog](benchmark_catalog.md)

This inventory contains papers that introduce a serious candidate benchmark,
establish an evaluation protocol, or provide a close baseline for an implemented
VidXP component. It is deliberately prioritized: “relevant” does not mean every
paper mentioning video retrieval, CLIP, ASR, or face recognition.

The paper-writing team can review these later. This workstream's immediate use is
to trace which datasets, metrics, baselines, and public artifacts each paper
actually relies on.

## Reading order

Start with these papers before reviewing individual model variants:

1. **TVR / XML** for the closest peer-reviewed corpus-level visual/transcript
   temporal-retrieval task.
2. **Localizing Moments in Video with Natural Language** for the simplest
   executable visual moment benchmark.
3. **QVHighlights / Moment-DETR** for modern interval and highlight evaluation.
4. **Zero-shot Video Moment Retrieval With Off-the-Shelf Models** for the closest
   methodological comparison to VidXP's untuned CLIP retrieval.
5. **HiREST** and **QuerYD** for speech-backed retrieval options.
6. **BCL** for unknown-number video face clustering and its WCP/NMI protocol.
7. **VPCD** and **C1C** for stronger person/track constraints and dataset context.
8. **LongVALE** for the strongest peer-reviewed combined vision–audio–speech
   temporal benchmark.
9. **Towards a Complete Benchmark on Video Moment Localization** for cross-dataset
   bias and evaluation methodology.

## Multimodal and whole-system retrieval

| Paper | Venue/year | Benchmarks introduced or used | Why it belongs |
| --- | --- | --- | --- |
| [TVR: A Large-Scale Dataset for Video-Subtitle Moment Retrieval](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123660443.pdf) | ECCV 2020 | Introduces TVR; VCMR, SVMR, VR | Closest established joint video/subtitle temporal benchmark |
| [HERO: Hierarchical Encoder for Video+Language Omni-representation Pre-training](https://aclanthology.org/2020.emnlp-main.161/) | EMNLP 2020 | TVR, TVQA, How2R, How2QA, VIOLIN | Major video-plus-subtitle representation baseline |
| [CONQUER: Contextual Query-aware Ranking for Video Corpus Moment Retrieval](https://arxiv.org/abs/2109.10016) | ACM MM 2021 | TVR and DiDeMo | Corpus moment-ranking comparator |
| [ReLoCLNet: Video Corpus Moment Retrieval with Contrastive Learning](https://26hzhang.github.io/publication/reloclnet/) | SIGIR 2021 | TVR/DiDeMo corpus retrieval lineage | Efficient separately encoded corpus-retrieval reference |
| [TVR-Ranking: A Real-World Dataset for Ranked Video Moment Retrieval](https://arxiv.org/abs/2407.06597) | SIGIR-AP 2025 | Introduces graded TVR-Ranking | Best graded ranked-search definition, with inherited TVR access limits |
| [VRAgent: Self-Refining Agent for Zero-Shot Multimodal Video Retrieval](https://openaccess.thecvf.com/content/WACV2026/html/Shah_VRAgent_Self-Refining_Agent_for_Zero-Shot_Multimodal_Video_Retrieval_WACV_2026_paper.html) | WACV 2026 | MM-MSRVTT and TVR-1200 | New visual/transcript/joint retrieval reference; public benchmark artifact not yet independently verified |
| [SAVE: Speech-Aware Video Representation Learning for Video-Text Retrieval](https://openaccess.thecvf.com/content/CVPR2026/html/Zhao_SAVE_Speech-Aware_Video_Representation_Learning_for_Video-Text_Retrieval_CVPR_2026_paper.html) | CVPR 2026 | MSR-VTT, VATEX, Charades, LSMDC | Speech-aware whole-video retrieval, but not timestamp localization |
| [LongVALE](https://openaccess.thecvf.com/content/CVPR2025/papers/Geng_LongVALE_Vision-Audio-Language-Event_Benchmark_Towards_Time-Aware_Omni-Modal_Perception_of_Long_Videos_CVPR_2025_paper.pdf) | CVPR 2025 | Introduces LongVALE | Strongest peer-reviewed vision–audio–speech temporal target; no actor task |
| [MultiVENT 2.0](https://openaccess.thecvf.com/content/CVPR2025/papers/Kriz_MultiVENT_2.0_A_Massive_Multilingual_Benchmark_for_Event-Centric_Video_Retrieval_CVPR_2025_paper.pdf) | CVPR 2025 | Introduces MultiVENT 2.0 | Large-corpus visual/audio/OCR/ASR/metadata retrieval; whole videos rather than moments |
| [MUVR](https://papers.neurips.cc/paper_files/paper/2025/hash/2a80c10b1fd6a6488a96cc1f4fbacc84-Abstract-Datasets_and_Benchmarks_Track.html) | NeurIPS Datasets & Benchmarks 2025 | Introduces MUVR | Large mixed-form query-to-video benchmark; only text subset aligns with current scene search |
| [FLARE](https://arxiv.org/abs/2605.10228) | arXiv 2026 | Introduces FLARE | Closest downloadable visual/audio/joint retrieval set; preprint and query-selection caveats |
| [TRECVID Ad-hoc Video Search overview](https://trec.nist.gov/pubs/trec33/papers/Overview_avs_vtt_actev.pdf) | TRECVID 2024 | V3C master-shot retrieval | Established large-corpus visual retrieval and xinfAP protocol |
| [SAVA: Search and Anchoring in Video Archives](https://ceur-ws.org/Vol-1436/Paper11.pdf) | MediaEval 2015 | BBC spoken-plus-visual interval retrieval | Historically close combined protocol; present data portability is not verified |

## Closest implemented systems

These papers are architectural and engineering comparators. They do not provide a
portable judged benchmark covering all of VidXP.

| Paper/system | Venue/year | Overlap | Benchmark status |
| --- | --- | --- | --- |
| [Multi-modal Video Search by Examples: A Video Quality Impact Analysis](https://doi.org/10.1049/cvi2.12303) | IET Computer Vision 2024 | Faces, scenes, speakers, ASR, fusion, approximate search over BBC video | Closest functional analogue; BBC data and judgments are not portable |
| [WISE: A Multimodal Search Engine for Visual Scenes, Audio, Objects, Faces, Speech, and Metadata](https://www.robots.ox.ac.uk/~vgg/publications/2026/sridhar2026wise/) | SIGIR 2026 | Scene/object/face, acoustic event, WhisperX speech, metadata, composite queries | Open-source system; deployments and latency context, no portable judged protocol |
| [ContextIQ](https://openaccess.thecvf.com/content/WACV2025/html/Chaubey_ContextIQ_A_Multimodal_Expert-Based_Video_Retrieval_System_for_Contextual_Advertising_WACV_2025_paper.html) | WACV 2025 | Video, audio, transcript, and metadata experts | Whole-video reference; supplemental annotations but no public implementation |
| [Collaborative Experts](https://www.robots.ox.ac.uk/~vgg/research/collaborative-experts/) | BMVC 2019 | Appearance, motion, scene, ASR, OCR, audio experts | Public models/features and corrected results; whole-video task |
| [Multi-Modal Transformer for Video Retrieval](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123490205.pdf) | ECCV 2020 | RGB, motion, scene, face, OCR, speech, audio experts | Multi-stream whole-video retrieval context |
| [MDMMT](https://openaccess.thecvf.com/content/CVPR2021W/HVU/html/Dzabraev_MDMMT_Multidomain_Multimodal_Transformer_for_Video_Retrieval_CVPRW_2021_paper.html) | CVPR Workshop 2021 | Multi-domain, multi-modal video retrieval | Model comparator across established short-video datasets |
| [VAST](https://proceedings.neurips.cc/paper_files/paper/2023/file/e6b2b48b5ed90d07c305932729927781-Paper-Conference.pdf) | NeurIPS 2023 | Vision–audio–subtitle representation | Retrieval/caption/QA model, not actor or native long-video search |
| [VALOR](https://arxiv.org/abs/2304.08345) | 2023 | Vision, audio, and language pretraining | Broad representation reference, not a matching end-to-end protocol |
| [CLaMR](https://arxiv.org/abs/2506.06144) | arXiv 2025 | Frame, ASR, OCR, and metadata late-interaction retrieval on MultiVENT/MSR-VTT | Relevant large-corpus fusion baseline; not peer-reviewed as verified |

## Dialogue, transcript, and speech retrieval

| Paper or evaluation | Venue/year | Benchmark relationship | Review purpose |
| --- | --- | --- | --- |
| [HiREST: Hierarchical Video-Moment Retrieval and Step-Captioning](https://openaccess.thecvf.com/content/CVPR2023/papers/Zala_Hierarchical_Video-Moment_Retrieval_and_Step-Captioning_CVPR_2023_paper.pdf) | CVPR 2023 | Introduces HiREST | Same Whisper plus MiniLM family as VidXP; practical speech-backed baseline |
| [Querying Videos by Natural Language Onsets](https://www.robots.ox.ac.uk/~vgg/publications/2021/Oncescu21/oncescu21.pdf) | ICASSP 2021 | Introduces QuerYD/QuerYDSegments | Public audio-description speech, text, and time labels |
| [TREC 2020 Podcasts Track Overview](https://trec.nist.gov/pubs/trec29/papers/OVERVIEW.P.pdf) | TREC 2020 | Podcast segment retrieval with graded judgments | Strong semantic spoken-content protocol; corpus distribution is closed |
| [OpenKWS 2013 Evaluation Plan](https://www.nist.gov/document/openkws13-evalplan-v4pdf) | NIST 2013 | Babel keyword search | Formal occurrence matching, ATWV, thresholds, indexing/search timing |
| [WhisperX: Time-Accurate Speech Transcription of Long-Form Audio](https://www.isca-archive.org/interspeech_2023/bain23_interspeech.html) | Interspeech 2023 | TED-LIUM timing/transcription experiments | Provenance and limitations of the alignment component; not a retrieval benchmark |
| [The MGB Challenge](https://www.cstr.ed.ac.uk/downloads/publications/2015/bell15_mgb_challenge.pdf) | ASRU 2015 | Broadcast ASR, diarization, and subtitle alignment | Speech-component evaluation lineage, not current end-to-end task |
| [mTVR: Multilingual Moment Retrieval in Videos](https://aclanthology.org/2021.acl-short.92/) | ACL-IJCNLP 2021 | Multilingual extension of TVR | Hold as reference; multilingual evaluation is not an intentional current claim |

Historical MediaEval Search & Hyperlinking and Rich Speech Retrieval work should be
reviewed for evaluation lineage, but the BBC licensing and old challenge
infrastructure make it unsuitable as the first executable benchmark.

## Visual moment and scene retrieval

| Paper | Venue/year | Benchmarks introduced or used | Why it belongs |
| --- | --- | --- | --- |
| [Localizing Moments in Video with Natural Language](https://arxiv.org/abs/1708.01641) | ICCV 2017 | Introduces DiDeMo | Defines the simplest first visual test and its 21-moment evaluator |
| [Moment-DETR: End-to-End Video Moment Retrieval with Natural Language](https://proceedings.neurips.cc/paper/2021/hash/62e0973455fd26eb03e91d5741a4a3bb-Abstract.html) | NeurIPS 2021 | Introduces QVHighlights | Primary modern interval/saliency benchmark |
| [Zero-shot Video Moment Retrieval With Off-the-Shelf Models](https://proceedings.mlr.press/v203/diwan23a.html) | Transfer Learning for NLP Workshop, PMLR 2023 | QVHighlights | Nearest zero-shot, off-the-shelf comparison to VidXP |
| [TALL: Temporal Activity Localization via Language Query](https://arxiv.org/abs/1705.02101) | ICCV 2017 | Introduces Charades-STA | Established, relatively manageable known-video interval benchmark |
| [Towards a Complete Benchmark on Video Moment Localization](https://proceedings.mlr.press/v238/chae24a.html) | AISTATS 2024 | Seven datasets; MoLEF framework | Cross-dataset bias, cost, and benchmark-methodology review |
| [QD-DETR: Query-Dependent Video Representation for Moment Retrieval and Highlight Detection](https://github.com/wjun0830/QD-DETR) | CVPR 2023 | QVHighlights, Charades-STA | Strong supervised comparator using the selected datasets |
| [UniVTG: Towards Unified Video-Language Temporal Grounding](https://github.com/showlab/UniVTG) | ICCV 2023 | QVHighlights, Charades-STA, Ego4D, TACoS | Cross-dataset supervised comparator |
| [VERIFIED: A Fine-Grained Benchmark for Video-Language Retrieval](https://proceedings.neurips.cc/paper_files/paper/2024/hash/477929b8d45ab759795b7aac94329b08-Abstract-Datasets_and_Benchmarks_Track.html) | NeurIPS 2024 | Hard-negative variants of Charades, DiDeMo, ActivityNet | Future robustness test; release completeness remains an issue |
| [MAD: A Scalable Dataset for Language Grounding in Videos from Movie Audio Descriptions](https://arxiv.org/abs/2112.00431) | CVPR 2022 | Introduces MAD | Long-film match, but raw movies are not distributed |
| [Ego4D](https://arxiv.org/abs/2110.07058) | CVPR 2022 | Includes Natural Language Queries | Strong long-video benchmark, deferred for access and compute cost |

## Whole-video CLIP-style retrieval

These papers are useful for scene-embedding baselines, but their headline task
ranks whole videos rather than locating timestamps.

| Paper | Typical benchmarks | Relevance |
| --- | --- | --- |
| [CLIP: Learning Transferable Visual Models From Natural Language Supervision](https://arxiv.org/abs/2103.00020) | Image-text transfer | Foundation of the current scene encoder; provenance, not a video benchmark |
| [CLIP4Clip](https://github.com/ArrowLuo/CLIP4Clip) | MSR-VTT, MSVD, LSMDC, ActivityNet, DiDeMo | Established CLIP video-text retrieval comparator |
| [Frozen in Time](https://github.com/m-bain/frozen-in-time) | MSR-VTT and other video-text sets | Retrieval baseline and practical MSR-VTT preparation route |
| [X-CLIP](https://github.com/xuguohai/X-CLIP) | MSR-VTT and related sets | Stronger supervised CLIP-style comparator |
| [MSR-VTT](https://www.microsoft.com/en-us/research/publication/msr-vtt-a-large-video-description-dataset-for-bridging-video-and-language/) | Introduces MSR-VTT | Corpus-ranking component benchmark, not temporal localization |

## Actor and video-face clustering

| Paper | Venue/year | Benchmarks introduced or used | Why it belongs |
| --- | --- | --- | --- |
| [Video Face Clustering With Unknown Number of Clusters](https://openaccess.thecvf.com/content_ICCV_2019/html/Tapaswi_Video_Face_Clustering_With_Unknown_Number_of_Clusters_ICCV_2019_paper.html) | ICCV 2019 | BBT and Buffy six-episode protocols; BCL | Primary reproducible clustering protocol, WCP/NMI, unknown K |
| [Constrained Video Face Clustering using 1NN Relations](https://www.bmvc2020-conference.com/assets/papers/0899.pdf) | BMVC 2020 | BBT, Buffy, Sherlock, Friends | Track-level constraints and broader TV protocol |
| [Face, Body, Voice: Video Person-Clustering with Multiple Modalities](https://openaccess.thecvf.com/content/ICCV2021W/CVEU/html/Brown_Face_Body_Voice_Video_Person-Clustering_With_Multiple_Modalities_ICCVW_2021_paper.html) | ICCV Workshop 2021 | Introduces VPCD | Closest face/body/voice system reference and labelled feature release |
| [VideoClusterNet: Self-Supervised and Unsupervised Face Clustering in Videos](https://www.ecva.net/papers/eccv_2024/papers_ECCV/html/4432_ECCV_2024_paper.php) | ECCV 2024 | MovieFaceCluster | Recent movie clustering baseline; dataset link is presently unavailable |
| [Self-supervised Video-centralised Transformer for Video Face Clustering](https://arxiv.org/abs/2203.13166) | arXiv 2022 | EasyCom-Clustering | Egocentric clustering reference; promised data remains unreleased |
| [Constrained Clustering and Its Application to Face Clustering in Videos](https://openaccess.thecvf.com/content_cvpr_2013/html/Wu_Constrained_Clustering_and_2013_CVPR_paper.html) | CVPR 2013 | Cast/face clustering protocols | Foundational cannot-link/must-link use in video |
| [Simultaneous Clustering and Tracklet Linking for Multi-face Tracking in Videos](https://openaccess.thecvf.com/content_iccv_2013/html/Wu_Simultaneous_Clustering_and_2013_ICCV_paper.html) | ICCV 2013 | Multi-face tracking/clustering | Shows why per-frame clustering and track-based evaluation differ |
| [End-To-End Face Detection and Cast Grouping in Movies Using Erdos-Renyi Clustering](https://openaccess.thecvf.com/content_iccv_2017/html/Jin_End-To-End_Face_Detection_ICCV_2017_paper.html) | ICCV 2017 | End-to-end detection and cast grouping | Closest methodology for evaluating missed detections plus clustering |
| [A Prior-Less Method for Multi-Face Tracking in Unconstrained Videos](https://openaccess.thecvf.com/content_cvpr_2018/html/Lin_A_Prior-Less_Method_CVPR_2018_paper.html) | CVPR 2018 | Multi-face tracking | Relevant if VidXP adds track formation before clustering |
| [Self-Supervised Learning of Face Representations for Video Face Clustering](https://arxiv.org/abs/1903.01000) | arXiv 2019 | Video face-clustering datasets | Representation-learning comparator, not an immediate benchmark package |
| [MovieNet: A Holistic Dataset for Movie Understanding](https://arxiv.org/abs/2007.10937) | ECCV 2020 | Introduces MovieNet | Cross-component characters, scenes, subtitles, and metadata |
| [MovieGraphs: Towards Understanding Human-Centric Situations from Videos](https://openaccess.thecvf.com/content_cvpr_2018/papers/Vicol_MovieGraphs_Towards_Understanding_CVPR_2018_paper.pdf) | CVPR 2018 | Introduces MovieGraphs | Character/interaction context; not a direct clustering benchmark |
| [Dynamic Character Graph via Online Face Clustering for Movie Analysis](https://arxiv.org/abs/2007.14913) | 2020 preprint | Movie character clustering/graphs | Close application context for chronological actor clustering |

## Evaluation-method papers and protocols

These sources matter because metric names alone can hide incompatible evaluation
units.

- The [IJB-B paper](https://openaccess.thecvf.com/content_cvpr_2017_workshops/w6/html/Whitelam_IARPA_Janus_Benchmark-B_CVPR_2017_paper.html)
  and [NIST protocol](https://www.nist.gov/system/files/documents/2021/06/07/ijbb_challenge_documentation_readme.pdf)
  define B-cubed precision, recall, and F-score for face clustering. Distribution
  ended in 2023, so this is protocol context unless the team already has lawful
  access.
- BCL and VPCD use WCP, NMI, and predicted cluster counts. Scores should not be
  mixed with IJB-B B-cubed results as if they were the same protocol.
- TVR, QVHighlights, and Charades-STA use non-zero temporal intervals and tIoU.
  VidXP's current point timestamp cannot be passed through those evaluators
  unchanged, but a deterministic interval adapter is sufficient for an
  evaluator-valid baseline.
- DiDeMo's mean IoU is computed over its constrained candidate grid and multiple
  human annotations; it is not interchangeable with unrestricted interval mAP.

## Review labels

When notes are added for the paper team, use one of these labels:

- **Benchmark-defining:** introduces a dataset or official evaluation.
- **Comparable zero-shot baseline:** can be run under the same frozen protocol
  without task-specific training.
- **Supervised comparator:** useful context but must be separated from zero-shot
  VidXP results.
- **Architecture/context only:** informs design but is not a numerical baseline.
- **Artifact blocked:** relevant paper whose media, code, or evaluator cannot
  currently support reproduction.

## Items that still need confirmation

- Exact accessible release, if any, for VRAgent's TVR-1200 annotations.
- Exact Creative Commons variant for TVR-Ranking.
- Explicit reuse license for QuerYD annotations and narrator audio.
- Current legal path to TVR clips with audio.
- Current raw-video survival rate for LongVALE and MultiVENT 2.0.
- Whether a corrected VPCD release or implementation has appeared outside the
  official project and GitHub pages.
- Whether the MovieFaceCluster dataset has moved from its now-broken paper link.
