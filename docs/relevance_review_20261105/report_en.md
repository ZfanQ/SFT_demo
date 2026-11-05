# Independent GPT Review of Saved Relevance Scores

Experiment started: November 5, 2026. Completed: November 6, 2026 (Asia/Shanghai).

GPT independently scored **60/60 paper–profile pairs** using the original 0–3 scale, providing exact abstract evidence and a relevance explanation. The saved model scores were then compared with these judgments, producing **540 paired comparisons** across three models and three concurrency settings.

Across the nine configurations, exact score agreement was **60.0%–80.0%**. Agreement on the score-2 relevance boundary was **91.7%–95.0%**. The priority queue isolates cases that can change whether an article is considered relevant.

## Design

- Three synthetic interest profiles: oncology, cardiovascular medicine and neuroscience.
- Twenty pairs per profile, randomly selected with seed 42: five from each saved Qwen3-8B/p2 score stratum. This balances the diagnostic sample across the scale.
- Each reviewer session receives the original task and abstract. Model names, prior scores, concurrency and sampling labels are withheld. Sessions run in isolated temporary directories with tools and browsing disabled.
- Judge: `gpt-6.1-sol`, medium reasoning, one independent session per pair. The original scale is retained; the response adds evidence, rationale and an explicit scope-ambiguity flag.
- Exact quotations, IDs, score types/ranges and provenance are checked before acceptance. Frozen source hashes and complete raw outputs support resumption and audit.

## Agreement with the GPT reference

| Saved configuration | Concurrency | Pairs | Exact agreement | Within one point | Mean absolute difference | Difference ≥2 | Relevant/not-relevant disagreements |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3_8b | 2 | 60 | 60.0% | 100.0% | 0.400 | 0 | 5 |
| qwen3_8b | 4 | 60 | 60.0% | 100.0% | 0.400 | 0 | 5 |
| qwen3_8b | 8 | 60 | 60.0% | 100.0% | 0.400 | 0 | 5 |
| qwen35_9b_llamacpp | 2 | 60 | 70.0% | 100.0% | 0.300 | 0 | 3 |
| qwen35_9b_llamacpp | 4 | 60 | 68.3% | 100.0% | 0.317 | 0 | 4 |
| qwen35_9b_llamacpp | 8 | 60 | 70.0% | 100.0% | 0.300 | 0 | 4 |
| gemma4_12b_llamacpp | 2 | 60 | 80.0% | 98.3% | 0.217 | 1 | 3 |
| gemma4_12b_llamacpp | 4 | 60 | 75.0% | 98.3% | 0.267 | 1 | 4 |
| gemma4_12b_llamacpp | 8 | 60 | 76.7% | 98.3% | 0.250 | 1 | 3 |

The relevant/not-relevant boundary is score 2: scores 0–1 versus 2–3. Differences are saved score minus GPT score. All configurations are compared on the same reviewed pairs.

## Cases for human review

The review flagged **4 scope-ambiguous pairs** and identified **7 high-priority pairs** with a difference of at least two points or a relevance-boundary disagreement. An additional **6 agreement controls** were selected from pairs where all saved configurations agree with GPT and the scope is unambiguous.

Start with [the independent scoring form](human_review/independent_scores.csv), recording a human score and reason before consulting GPT judgments. Then use [the priority queue](human_review/priority_queue.csv) to inspect disagreements, ambiguous scope and agreement controls.

| Profile | Paper | Priority | GPT score | Largest score difference | Configurations crossing threshold | Scope ambiguous |
| --- | --- | --- | ---: | ---: | ---: | --- |
| neuroscience | paper195 | high | 0 | 2 | 3 | False |
| cardiovascular | paper066 | high | 1 | 1 | 9 | False |
| cardiovascular | paper061 | high | 1 | 1 | 8 | False |
| cardiovascular | paper076 | high | 1 | 1 | 6 | True |
| oncology | paper152 | high | 1 | 1 | 6 | False |
| oncology | paper053 | high | 1 | 1 | 3 | False |
| cardiovascular | paper080 | high | 1 | 1 | 1 | False |
| cardiovascular | paper009 | medium | 2 | 1 | 0 | True |
| neuroscience | paper024 | medium | 1 | 1 | 0 | True |
| cardiovascular | paper003 | medium | 1 | 0 | 0 | True |
| cardiovascular | paper058 | low | 0 | 0 | 0 | False |
| cardiovascular | paper067 | low | 3 | 0 | 0 | False |
| neuroscience | paper019 | low | 3 | 0 | 0 | False |
| neuroscience | paper078 | low | 3 | 0 | 0 | False |
| oncology | paper006 | low | 0 | 0 | 0 | False |
| oncology | paper010 | low | 3 | 0 | 0 | False |

## Interpretation and next step

The results measure agreement with an independent GPT reference on a deliberately score-balanced sample. Each pair has one accepted GPT judgment. Agreement percentages describe this balanced cohort. Human labels are the next step for measuring scoring accuracy. Profile scope remains the original coarse definition, so ambiguous boundaries are documented for later rubric refinement.

Review the priority cases and agreement controls, reconcile profile boundaries, and record human judgments. Any refined scale or profile should create a new evaluation version, preserving the original 5,400 model scores.

Detailed records: [configuration summary](configuration_summary.csv), [per-profile metrics](per_profile_summary.csv), [all paired comparisons](comparisons.csv), `inputs/selection.json`, and `gpt_reviews/protocol.json`.
