# Relevance Scoring: Performance and Independent GPT Agreement

Updated: November 6, 2026. Performance measurements: October 31; full GPT review: November 6.

## Findings

Qwen3-8B provides the highest measured scoring rate. Qwen3.5-9B agrees most often with the independent GPT scores, while Gemma-4-12B has fewer disagreements at the relevant/not-relevant threshold. Concurrency 4 offers a useful working balance: increasing to 8 adds 2.5–6.7% throughput while nearly doubling p95 latency.

The review is complete for 200 abstracts and three fixed interest profiles (600 distinct tasks). It compares the same saved outputs from all nine model/concurrency configurations: 5,400 timed responses and 5,400 comparisons. GPT judgments are automated references; independent human calibration is pending and assigned to the teammate.

## Combined results

| Model | Backend | Concurrency | Scores/min | p95 latency (s) | GPT exact agreement | Mean absolute difference | Difference ≥2 | Relevance-boundary disagreements |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B | Ollama | 2 | 101.08 | 1.358 | 75.5% | 0.255 | 6 | 19 |
| Qwen3-8B | Ollama | 4 | 113.75 | 2.403 | 75.8% | 0.250 | 5 | 18 |
| Qwen3-8B | Ollama | 8 | 120.69 | 4.668 | 75.8% | 0.250 | 5 | 18 |
| Qwen3.5-9B | llama.cpp | 2 | 66.01 | 2.520 | 86.0% | 0.145 | 3 | 16 |
| Qwen3.5-9B | llama.cpp | 4 | 74.31 | 4.308 | 86.5% | 0.142 | 4 | 16 |
| Qwen3.5-9B | llama.cpp | 8 | 79.29 | 8.102 | 86.7% | 0.142 | 5 | 16 |
| Gemma-4-12B | llama.cpp | 2 | 41.69 | 3.370 | 84.3% | 0.158 | 1 | 11 |
| Gemma-4-12B | llama.cpp | 4 | 48.38 | 5.595 | 84.8% | 0.153 | 1 | 11 |
| Gemma-4-12B | llama.cpp | 8 | 49.58 | 11.165 | 85.2% | 0.150 | 1 | 9 |

Each row uses the same 600 paper/profile tasks. Scores/minute counts one abstract scored for one profile. p95 latency is the time within which 95% of active request paths complete. Exact agreement means identical 0–3 scores; mean absolute difference measures their average numerical gap. The relevance boundary separates scores 0–1 from scores 2–3. A 1-versus-2 disagreement can therefore affect recommendation inclusion despite being only one point apart.

## Practical trade-off

At concurrency 4, Qwen3-8B processes 113.75 scores/minute at 2.403 s p95 latency, with 75.8% GPT exact agreement. Qwen3.5-9B processes 74.31 scores/minute at 4.308 s and reaches 86.5% agreement, a 10.7 percentage-point increase at about 35% lower throughput. Gemma processes 48.38 scores/minute at 5.595 s, with 84.8% agreement and 11 threshold disagreements versus 16 for 9B and 18 for 8B.

Use these configurations as candidates for human-calibrated selection: 8B when throughput dominates, 9B when matching the ordinal reference is the priority, and Gemma when threshold decisions deserve particular attention. The application latency target and human decisions determine the final choice. Small observed differences between concurrency settings come from one measured pass per cell.

## Reference distribution and interpretation

GPT assigns score 0 to 468/600 tasks (78.0%). An always-zero classifier therefore achieves 78.0% exact agreement. GPT marks 86/600 tasks relevant (score ≥2), so an always-not-relevant classifier agrees on the binary threshold for 85.7% of tasks. Interpret total agreement alongside threshold disagreements and per-profile results; these rates are agreement with GPT rather than human-validated accuracy or ranking quality.

At concurrency 4, 9B exact agreement is 90.5% for oncology, 85.0% for cardiovascular medicine and 84.0% for neuroscience. Profile-specific reference distributions differ. [Per-profile statistics](per_profile_gpt_agreement.csv) retain all models and concurrency levels.

## Matched protocol and provenance

The original task is abstract plus interest profile → integer relevance: 0 unrelated, 1 peripheral, 2 relevant, 3 directly relevant. The frozen collection has 200 papers and three synthetic profiles: oncology, cardiovascular medicine and neuroscience. Dataset SHA-256: `d7167d37541c88eb8f98a36f117821f467174680107990cfccd4b0c63410949a`.

Performance: the existing H100 MIG/vGPU allocation; Q4_K_M weights; 4,096-token context; 96-token output cap; temperature 0; seed 42; thinking disabled. Each round has held-out warmup and a fresh private service. Throughput includes request handling, inference, validation and ledger writes; startup, model loading and warmup are excluded. Latency includes request preparation, service queuing and inference, but excludes validation and ledger writes. All 5,400 accepted responses were independently checked against inputs and raw outputs, with full GPU-layer offload and measured overlap verified.

8B uses Ollama; 9B and Gemma use direct llama.cpp after recorded frontend compatibility issues. Cross-model rates compare complete inference configurations, including templates and backends. Memory is sampled approximately once per second; compute-utilization telemetry is unavailable. This is short-output relevance scoring, so full-paper summarization requires a separate benchmark.

GPT review: requested model `gpt-6.1-sol`, medium reasoning, one task per isolated session, tools disabled. Prior scores, model identity and concurrency are hidden. The original rubric and profiles are retained. Sixty pilot judgments and raw records are reused byte for byte; 540 new judgments complete the collection. IDs, exact source quotations, schema and hashes were checked; all 600 accepted judgments passed on their first mechanical-validation attempt.

## Human calibration and next decision

The teammate has all 600 independent scoring tasks and a reconciliation queue containing 28 high-priority pairs, 24 scope ambiguities and 20 agreement controls; categories can overlap. High priority indicates at least one two-point discrepancy or relevance-boundary disagreement across nine configurations. Human reviewers first score the hidden-reference form, then compare evidence and resolve scope boundaries. Review findings will determine whether to refine profiles, prompts or rubric and which configuration to carry forward. Summary factuality remains a separate workstream.

## Supporting records

- [Performance report and reproducibility records](https://github.com/ZfanQ/SFT_demo/blob/f5e25e269b4734a2790f2e2f0b2455c66f90739d/experiments/performance/feed_matrix_20261031/report_en.md).
- [Full independent relevance review](https://github.com/ZfanQ/SFT_demo/blob/f5e25e269b4734a2790f2e2f0b2455c66f90739d/experiments/relevance/relevance_review_full_20261106/report_en.md).
- [Human calibration packet](https://github.com/ZfanQ/SFT_demo/blob/f5e25e269b4734a2790f2e2f0b2455c66f90739d/experiments/relevance/relevance_review_full_20261106/human_review/priority_queue.csv).
- [Combined numerical results](combined_results.csv), [per-profile agreement](per_profile_gpt_agreement.csv) and [source manifest](provenance.json).

Experimental source commit: `f5e25e269b4734a2790f2e2f0b2455c66f90739d`. Published by explicit user request as a combined progress report with human calibration pending.
