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
   benchmark matrix, access constraints, recommended suite, feasibility checks,
   and execution order.
3. [Research-paper inventory](research_papers.md) is the prioritized reading queue
   and maps relevant papers to the benchmarks they introduce or use.

## Current conclusion

No single published benchmark covers VidXP's dialogue retrieval, visual scene
retrieval, and actor clustering together. The current recommendation is a
component suite led by DiDeMo, QVHighlights, TVR or its speech-backed alternatives,
and BCL, with LongVALE reserved for a later combined vision–audio–speech test.

The next gate is benchmark feasibility: confirm media access, licenses, evaluator
availability, storage, and processing cost. Adapter implementation starts only
after that review.

## Historical material

[Legacy benchmarking methodology](../benchmarking_research.md) is retained at its
original location and filename for provenance
because it contains useful earlier notes and published reference points. It is not
the current plan: its Urdu assumption and proposed custom-corpus direction were
superseded by the published-benchmark-first audit.
