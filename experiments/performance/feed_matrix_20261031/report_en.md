# Medical Feed Concurrency Matrix: 200 Abstracts and Three Interest Profiles

Date: October 31, 2026.

## Findings

Qwen3-8B achieved the highest measured throughput: **120.69 paper/profile scores/minute** at concurrency 8. At concurrency 4, it processed **113.75 scores/minute** with p95 latency **2.403 s**, compared with **4.668 s** at the throughput maximum.

The benchmark evaluated 5,400 independently verified timed requests across 3 model configurations. Each complete matrix scores 200 frozen abstracts for three research-interest profiles at concurrency 2, 4 and 8: 600 distinct paper/profile inputs and 1,800 timed requests per model. All three matrices are complete.

The experiment measures the throughput, latency, GPU-layer offload and score stability of independent-abstract relevance scoring. The Qwen3-8B matrix was completed and verified before the upgraded-model stages.

## Combined throughput and latency

| Model | Backend | Concurrent requests | Profiles | Timed requests | Paper/profile scores per min | Median latency (s) | p95 latency (s) | Peak sampled memory (MiB) | Output tokens/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B | ollama | 2 | 3 | 600 | 101.08 | 1.184 | 1.358 | 6329 | 52.80 |
| Qwen3-8B | ollama | 4 | 3 | 600 | 113.75 | 2.058 | 2.403 | 7455 | 59.17 |
| Qwen3-8B | ollama | 8 | 3 | 600 | 120.69 | 3.931 | 4.668 | 9767 | 62.72 |
| Qwen3.5-9B | llama_cpp | 2 | 3 | 600 | 66.01 | 1.785 | 2.520 | 5445 | 30.08 |
| Qwen3.5-9B | llama_cpp | 4 | 3 | 600 | 74.31 | 3.169 | 4.308 | 5803 | 34.19 |
| Qwen3.5-9B | llama_cpp | 8 | 3 | 600 | 79.29 | 5.849 | 8.102 | 6515 | 36.82 |
| Gemma-4-12B | llama_cpp | 2 | 3 | 600 | 41.69 | 2.831 | 3.370 | 8431 | 28.49 |
| Gemma-4-12B | llama_cpp | 4 | 3 | 600 | 48.38 | 4.891 | 5.595 | 9515 | 33.06 |
| Gemma-4-12B | llama_cpp | 8 | 3 | 600 | 49.58 | 9.647 | 11.165 | 11693 | 33.88 |

Throughput is total completed requests divided by summed timed durations, expressed as paper/profile scores per minute. Each request scores one paper for one profile; each profile contributes the same 200 articles. Latency runs from worker request-path start to receipt of the decoded response, including request preparation, service queuing and inference; output validation, ledger writing and waiting for a free client worker fall outside that latency measurement.

## Throughput and latency tradeoff

![Throughput and active-request latency](throughput_latency.png)

Each point aggregates 600 requests; labels give concurrency. Qwen3-8B uses Ollama and both upgraded models use direct llama.cpp.

- Qwen3-8B: highest observed throughput at **8 requests**, **120.69 paper/profile scores/minute**, **+19.4%** against its 2-request baseline; p95 latency **4.668 s**.
- Qwen3.5-9B: highest observed throughput at **8 requests**, **79.29 paper/profile scores/minute**, **+20.1%** against its 2-request baseline; p95 latency **8.102 s**.
- Gemma-4-12B: highest observed throughput at **8 requests**, **49.58 paper/profile scores/minute**, **+18.9%** against its 2-request baseline; p95 latency **11.165 s**.

Concurrency 4 offers a practical throughput/latency balance for the next relevance-quality evaluation. Moving to 8 produces a modest throughput gain while nearly doubling p95 latency:

| Model | Throughput gain: 4 to 8 | p95 latency at 4 (s) | p95 latency at 8 (s) |
| --- | ---: | ---: | ---: |
| Qwen3-8B | +6.1% | 2.403 | 4.668 |
| Qwen3.5-9B | +6.7% | 4.308 | 8.102 |
| Gemma-4-12B | +2.5% | 5.595 | 11.165 |

Use concurrency 8 when batch completion rate has priority; evaluate concurrency 4 when individual response time also matters. Final selection depends on the application's latency target and independently assessed relevance quality.

### Illustrative workload arithmetic

The meeting's illustrative scenario of 10,000 abstracts/day and about 20 profiles requires 200,000 pointwise scoring requests. Applying each configuration's highest observed throughput gives:

| Model | Selected concurrency | Hours for 200,000 scores |
| --- | ---: | ---: |
| Qwen3-8B | 8 | 27.6 |
| Qwen3.5-9B | 8 | 42.0 |
| Gemma-4-12B | 8 | 67.2 |

This extrapolation assumes the measured input-length/profile mix, service rate and continuous availability; feed retrieval, summarization and other pipeline work require additional time. The arrival volume is a scenario from the discussion. The estimates motivate testing semantic prefiltering and multiple abstracts per prompt.

## Per-profile rounds

| Model | Profile | Concurrent requests | Valid / expected | Scores/min | p95 latency (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen3-8B | oncology | 2 | 200 / 200 | 100.63 | 1.358 |
| Qwen3-8B | oncology | 4 | 200 / 200 | 114.27 | 2.404 |
| Qwen3-8B | oncology | 8 | 200 / 200 | 116.56 | 5.072 |
| Qwen3-8B | cardiovascular | 2 | 200 / 200 | 99.61 | 1.367 |
| Qwen3-8B | cardiovascular | 4 | 200 / 200 | 109.84 | 2.380 |
| Qwen3-8B | cardiovascular | 8 | 200 / 200 | 119.92 | 4.709 |
| Qwen3-8B | neuroscience | 2 | 200 / 200 | 103.06 | 1.314 |
| Qwen3-8B | neuroscience | 4 | 200 / 200 | 117.39 | 2.398 |
| Qwen3-8B | neuroscience | 8 | 200 / 200 | 125.95 | 4.427 |
| Qwen3.5-9B | oncology | 2 | 200 / 200 | 64.48 | 2.491 |
| Qwen3.5-9B | oncology | 4 | 200 / 200 | 71.37 | 4.383 |
| Qwen3.5-9B | oncology | 8 | 200 / 200 | 80.30 | 8.038 |
| Qwen3.5-9B | cardiovascular | 2 | 200 / 200 | 69.43 | 2.529 |
| Qwen3.5-9B | cardiovascular | 4 | 200 / 200 | 74.27 | 4.371 |
| Qwen3.5-9B | cardiovascular | 8 | 200 / 200 | 74.95 | 8.557 |
| Qwen3.5-9B | neuroscience | 2 | 200 / 200 | 64.36 | 2.471 |
| Qwen3.5-9B | neuroscience | 4 | 200 / 200 | 77.53 | 4.168 |
| Qwen3.5-9B | neuroscience | 8 | 200 / 200 | 83.06 | 7.452 |
| Gemma-4-12B | oncology | 2 | 200 / 200 | 41.64 | 3.421 |
| Gemma-4-12B | oncology | 4 | 200 / 200 | 49.13 | 5.418 |
| Gemma-4-12B | oncology | 8 | 200 / 200 | 48.55 | 11.151 |
| Gemma-4-12B | cardiovascular | 2 | 200 / 200 | 42.01 | 3.217 |
| Gemma-4-12B | cardiovascular | 4 | 200 / 200 | 48.16 | 5.691 |
| Gemma-4-12B | cardiovascular | 8 | 200 / 200 | 48.88 | 11.165 |
| Gemma-4-12B | neuroscience | 2 | 200 / 200 | 41.43 | 3.442 |
| Gemma-4-12B | neuroscience | 4 | 200 / 200 | 47.86 | 5.676 |
| Gemma-4-12B | neuroscience | 8 | 200 / 200 | 51.42 | 11.004 |

Observed input-token ranges, including instructions/profile and source-specific templates:

| Model | Minimum | Maximum |
| --- | ---: | ---: |
| Qwen3-8B | 326 | 840 |
| Qwen3.5-9B | 325 | 843 |
| Gemma-4-12B | 306 | 834 |

## Ordinal-score and ranking stability

Each request returns only the article ID, profile ID and an integer relevance score: 0 unrelated, 1 peripheral, 2 relevant, 3 directly relevant. The table compares each model with its own 2-request outputs. Spearman correlation uses average ranks for ties. Threshold flips cross the boundary between scores below 2 and scores at least 2.

| Model | Profile | Parallel vs 2 | Exact score agreement | Mean absolute score change | Relevant/not-relevant flips | Spearman (tied ranks) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B | oncology | 4 | 98.5% | 0.015 | 0 / 200 | 0.9989 |
| Qwen3-8B | oncology | 8 | 98.5% | 0.015 | 0 / 200 | 0.9830 |
| Qwen3-8B | cardiovascular | 4 | 98.0% | 0.020 | 0 / 200 | 0.9832 |
| Qwen3-8B | cardiovascular | 8 | 98.0% | 0.020 | 0 / 200 | 0.9751 |
| Qwen3-8B | neuroscience | 4 | 98.0% | 0.020 | 1 / 200 | 0.9738 |
| Qwen3-8B | neuroscience | 8 | 95.0% | 0.050 | 1 / 200 | 0.9220 |
| Qwen3.5-9B | oncology | 4 | 99.0% | 0.010 | 1 / 200 | 0.9925 |
| Qwen3.5-9B | oncology | 8 | 98.0% | 0.020 | 1 / 200 | 0.9776 |
| Qwen3.5-9B | cardiovascular | 4 | 94.5% | 0.055 | 2 / 200 | 0.8986 |
| Qwen3.5-9B | cardiovascular | 8 | 95.0% | 0.050 | 3 / 200 | 0.9208 |
| Qwen3.5-9B | neuroscience | 4 | 98.5% | 0.015 | 1 / 200 | 0.9883 |
| Qwen3.5-9B | neuroscience | 8 | 98.0% | 0.020 | 0 / 200 | 0.9773 |
| Gemma-4-12B | oncology | 4 | 97.0% | 0.030 | 0 / 200 | 0.9663 |
| Gemma-4-12B | oncology | 8 | 96.5% | 0.035 | 0 / 200 | 0.9597 |
| Gemma-4-12B | cardiovascular | 4 | 98.5% | 0.015 | 1 / 200 | 0.9805 |
| Gemma-4-12B | cardiovascular | 8 | 97.5% | 0.025 | 1 / 200 | 0.9616 |
| Gemma-4-12B | neuroscience | 4 | 97.0% | 0.030 | 3 / 200 | 0.9832 |
| Gemma-4-12B | neuroscience | 8 | 97.5% | 0.025 | 3 / 200 | 0.9904 |

### Score distributions at concurrency 2

| Model | Profile | Score 0 | Score 1 | Score 2 | Score 3 |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen3-8B | oncology | 106 | 53 | 5 | 36 |
| Qwen3-8B | cardiovascular | 131 | 46 | 14 | 9 |
| Qwen3-8B | neuroscience | 137 | 38 | 14 | 11 |
| Qwen3.5-9B | oncology | 141 | 18 | 6 | 35 |
| Qwen3.5-9B | cardiovascular | 150 | 34 | 7 | 9 |
| Qwen3.5-9B | neuroscience | 157 | 18 | 14 | 11 |
| Gemma-4-12B | oncology | 128 | 33 | 4 | 35 |
| Gemma-4-12B | cardiovascular | 140 | 41 | 8 | 11 |
| Gemma-4-12B | neuroscience | 131 | 36 | 16 | 17 |

These distributions show how each model uses the relevance scale. Class imbalance can raise exact agreement; interpret it together with threshold flips and tied-rank correlation.

## Reproducible protocol

- Frozen inputs: all 200 existing abstracts and three synthetic researcher-interest profiles (oncology, cardiovascular medicine, neuroscience). The seed-42 article order is reused across configurations and models.
- Profile-specific concurrency order: oncology 2–4–8, cardiovascular 4–8–2, neuroscience 8–2–4.
- Common request options: 4,096-token context, 96-token output cap, temperature 0, seed 42, thinking disabled. The upgraded-model aliases explicitly match the old Qwen effective presence/repetition penalties and top-k/top-p/min-p settings; source-specific templates and stop tokens remain intact.
- Warmup: 2 × concurrency synthetic held-out abstract requests at the target concurrency, excluded from timing. Every timed round starts a fresh private service on loopback port 11437.
- Timed-round throughput includes request-path template rendering/tokenization, HTTP handling, queuing, inference, validation and serialized raw-ledger writes. Input preparation, standalone preflight tokenization, server startup, model load and warmup are excluded. Prefix caching remains enabled.
- Each accepted round must contain exactly 200 unique article/profile records, valid structured scores and normal completion. Failed or interrupted attempts remain stored and are excluded from accepted-round aggregates.
- Independent validation re-parses raw responses, checks input hashes and token budget, recomputes all timing aggregates, verifies full GPU-layer offload and inspects measured overlapping execution slots in backend logs.
- Hardware: the existing H100 MIG/vGPU allocation. Memory is sampled approximately once per second; backend logs record full transformer-layer offload and host buffers. Monitoring checks the shared Ollama service for competing activity.
- Original abstracts are hash-checked after each complete model. Saved summaries and shared Ollama service settings remain unchanged.

## Model provenance

| Report label | Registered model / source reference | Quantization | Model digest |
| --- | --- | --- | --- |
| Qwen3-8B | `qwen3:8b` | Q4_K_M | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| Qwen3.5-9B | `study-qwen35-9b-q4:20261031` | Q4_K_M | `06b156770b19881c72b422487e29562bb0947b1e99701664ecdd6554e3b407b2` |
| Gemma-4-12B | `study-gemma4-12b-q4:20261031` | Q4_K_M | `af0afe213c2a534eefff293f72cc776b9e49cf8f612eb01396f1fe132f2869e8` |

Qwen3.5-9B source checkpoint: `qwen3.5:9b-q4_K_M`, digest `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
Gemma-4-12B source checkpoint: `gemma4:12b-it-q4_K_M`, digest `6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b`.

Qwen3.5-9B uses direct llama.cpp with the same Q4_K_M checkpoint after the Ollama 0.34.4 scheduler forced `qwen35` to one slot. The driver applies the pinned official HF template/tokenizer and checks representative token-ID parity, full GPU-layer offload and per-slot context each round. The original scheduler and binary remain unchanged. Startup diagnostics and the eight-request smoke test are preserved outside measured aggregates.

Gemma-4-12B uses direct llama.cpp text-only inference after Ollama stalled during empty-input initialization. The configuration skips that startup warmup, retains synthetic real-request warmup, and uses the embedded GGUF template/tokenizer with thinking off. Each round checks all 200 prompts for preserved system/user text and context budget. [Compatibility evidence](compatibility_notes_en.md) records both backend adjustments.

## Interpretation

The measurements compare complete inference configurations. Cross-model rates reflect architecture, Q4_K_M weights, frontend and template differences; within-model concurrency comparisons use the same workload and configuration. The Gemma run uses Q4_K_M weights, whereas the historical full-paper summary evaluation used HF bitsandbytes NF4.

Agreement and correlation measure score stability relative to each model's 2-request outputs. Independent relevance labels are needed to assess correctness and ranking quality. Each paper/profile/concurrency cell has one measured pass. Profile orders balance configuration position; repeated runs at the same setting are needed to estimate timing and score variability.

This saturated closed-loop workload uses a historical abstract collection and synthetic profiles. Transfer to a live feed depends on its input lengths, profile mix and arrival pattern. Full-paper summarization requires its own long-context, long-output benchmark. Output-token rates use each model's tokenizer.

GPU compute-utilization telemetry is unavailable, so resource reporting covers sampled memory and layer placement. Shared-service monitoring covers Ollama activity; other GPU work may affect timing. Gemma's embedded tokenizer was checked for input integrity and context budget; independent official-HF token-ID parity remains unverified. Its successful startup adjustment changes the frontend and warmup configuration together, leaving the original stall's kernel cause unresolved.

## Reproducibility and next steps

Dataset SHA-256: `d7167d37541c88eb8f98a36f117821f467174680107990cfccd4b0c63410949a`.

Per-model `analysis.json` contains verified per-profile and combined measurements, engine evidence and the complete score-variation list. Each round retains its model-residency snapshot, server log, warmup responses, timed JSONL responses, GPU samples and status. Source checkpoints, alias settings, inherited model metadata and exact script hashes are preserved.

Next, assess relevance on a preselected independently reviewed sample, examine concurrency-dependent score changes, and compare rankings with the existing semantic baseline on matched inputs. Then test multiple abstracts per prompt at fixed GPU concurrency, using stable article IDs and cross-batch anchors. Together, these checks will support a configuration choice based on relevance quality, throughput and latency.

Server experiment root: `/data/SFT_demo/Oct/results/feed_matrix_20261031/`.
