# VidXP benchmarking research

This directory is the entry point for the paper-benchmarking workstream. Its scope
is to identify published benchmarks, verify that their data and evaluators can
actually be obtained, and select the smallest credible suite for the capabilities
implemented in `main.py`.

It does not cover editing the paper itself, and it does not treat a published score
as directly comparable until VidXP is run on the same data, output protocol, and
evaluator.

## Start here

1. [Direction and source of truth](direction.md) defines the scope, evidence
   requirements, classification rules, and execution gates.
2. [Published benchmark catalog](benchmark_catalog.md) contains the validated
   benchmark matrix, including what every candidate measures, what its result would
   and would not demonstrate about VidXP, access constraints, and execution order.
3. [Published comparison results](published_results.md) records exact competitor
   scores, splits, training status, primary-paper table/page citations, and
   official artifacts without merging incompatible protocols.
4. [Execution readiness](execution_readiness.md) records the corrected engineering
   boundary and identifies which benchmarks can be run after lightweight API and
   adapter changes.
5. [Research-paper inventory](research_papers.md) is the prioritized reading queue
   and maps relevant papers to the benchmarks they introduce or use.
6. [Paper-by-paper validation ledger](paper_validation.md) records the experimental
   datasets, protocols, metrics, artifact checks, and corrections verified from
   each primary paper rather than inferred from its title or abstract.

## Current conclusion

No single published benchmark covers VidXP's dialogue retrieval, visual scene
retrieval, and actor clustering together. The current recommendation is a
component suite led by DiDeMo, QVHighlights, TVR or its speech-backed alternatives,
and BCL.

The paper-use audit now tracks 79 unique primary papers. Each inventory entry is
mapped to the datasets, protocol, and metrics it actually used in
[the validation ledger](paper_validation.md); this prevents pretraining corpora,
adapted tasks, and title-level relevance from being counted as benchmark evidence.

The current top-1 point-returning API is not a scientific constraint. Stable IDs,
top-k results, scores, intervals, metadata, aggregation, and serializers are normal
benchmark plumbing. DiDeMo and transcript-backed HiREST are ready to begin after
that shared adapter; TVR and BCL remain desirable but media-gated.

## Historical material

[Legacy benchmarking methodology](../benchmarking_research.md) is retained at its
original location and filename for provenance
because it contains useful earlier notes and published reference points. It is not
the current plan: its Urdu assumption and proposed custom-corpus direction were
superseded by the published-benchmark-first audit.
