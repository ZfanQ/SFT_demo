# Qwen3-8B Abstract Batching Pilot

Date: October 31, 2026.

## Result and scope

The private Ollama backend processed overlapping independent requests on the available H100 MIG allocation. Both six-round experiments completed: **384/384 measured requests** returned valid paper IDs and integer relevance scores with normal completion. No source abstracts changed. This is a short-output relevance-scoring throughput pilot, not full-paper summarization or a validated ranking-quality evaluation.

Under representative parallel warmup, the best observed configuration was **4 concurrent requests**, at **135.70 documents/minute**, a **+46.0%** change relative to its paired serial baseline. It is a candidate setting for a larger quality-controlled test, not a proven optimum.

## Representative parallel warmup: primary comparison

Each fresh private server was warmed with 2 × concurrency actual abstract requests submitted through the target number of workers (nominally two waves, with no barrier between them). Warmup articles were disjoint from the measured 32-paper set. Warmup requests are excluded from timing and the 384-inference total. All other workload and model settings match the initial pilot.

| Concurrent requests | Inferences | Valid | Documents/min | Change vs serial | Output tokens/s | Median latency (s) | p95 latency (s) | Peak sampled memory (MiB) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 64 | 64 | 92.93 | +0.0% | 29.04 | 0.642 | 0.740 | 5615 |
| 2 | 64 | 64 | 122.18 | +31.5% | 37.93 | 0.957 | 1.199 | 6279 |
| 4 | 64 | 64 | 135.70 | +46.0% | 42.26 | 1.739 | 2.074 | 7447 |

## Initial pilot: retained startup sensitivity check

The initial pilot warmed each server with one short request. Its four-way rounds differed substantially, and the first parallel requests had elevated latency. This motivated the second experiment; no initial observations were discarded or pooled into the primary table. Different warmup policies can alter startup state and prefix-cache behavior, so their difference is not proof of one isolated cause.

| Concurrent requests | Inferences | Valid | Documents/min | Change vs serial | Output tokens/s | Median latency (s) | p95 latency (s) | Peak sampled memory (MiB) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 64 | 64 | 92.84 | +0.0% | 29.98 | 0.635 | 0.750 | 5607 |
| 2 | 64 | 64 | 122.02 | +31.4% | 37.12 | 0.960 | 1.156 | 6275 |
| 4 | 64 | 64 | 97.54 | +5.1% | 31.19 | 1.748 | 7.358 | 7445 |

## Protocol

- Model: installed `qwen3:8b`, Q4_K_M; Ollama 0.34.4; model digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`. No model download or upgrade.
- Data: 32 abstracts sampled from the existing 200-paper collection, eight from each token-length quartile, with seed 42 and one fixed seeded ordering. Each concurrency receives the same 32 measured prompts twice, in sequence 1–2–4–4–2–1.
- Workload: one independent abstract per request, one oncology research-interest profile, relevance scale 0–3. The JSON output contains only paper ID and relevance. This tests request batching, not concatenating multiple abstracts into one context. It does not compare different user profiles or an existing semantic ranker.
- Context: 4,096 tokens; output cap: 96 tokens; temperature 0; seed 42; thinking disabled. Observed input counts in the primary comparison are 336–713 tokens and output counts 18–22 tokens. No input exceeded the reserved context budget.
- One model per private server, loopback port 11436, requested parallelism 1, 2 or 4. The existing shared service on port 11434 was read for inventory/activity and was not reconfigured. Each private server was terminated after its round. The existing model remained installed.
- Timings exclude reading, tokenization, server startup and warmup; they include request/response handling, queuing, generation, validation and raw response writes. Group throughput is total documents divided by summed round durations. Median and p95 use all 64 request latencies per setting; p95 is a linearly interpolated sample percentile. Prefix caching remains enabled.
- Memory is sampled approximately once per second. GPU compute utilization is unavailable on this allocation; memory occupancy is not compute utilization or evidence of saturation. Monitoring checks the shared Ollama model state; other processes or activity outside this check cannot be completely ruled out.

## Engine evidence and output checks

Private engine logs record `n_seq_max` of 1, 2 and 4 and overlapping active task slots reaching exactly those counts during measured requests. Every measured task has a matching release. The model was GPU-resident in all rounds. The engine also adjusts its configured token batch with parallelism; this is an end-to-end Ollama configuration comparison, not an isolated client-thread or fixed-kernel-batch experiment. This evidence goes beyond client HTTP overlap, but no CUDA kernel profiler was run.

All 384 raw responses were independently re-parsed; IDs, score type/range, completion, context budget and output hashes were checked. All 12 per-round throughputs and the grouped means were recalculated from raw rows. The 200 original abstract hashes were checked after each pilot. The scripts, prompt snapshots, engine logs, GPU samples and raw responses remain alongside these results.

Score disagreements versus the first serial round in the primary experiment (over 64 observations per setting) are: [(1, 0), (2, 3), (4, 5)]. These include repeated serial observations and are indicators of output repeatability only. A changed score may arise from batching, numerics, prompt caching or selection of a different valid response. There are no gold relevance labels, so neither agreement nor valid JSON certifies correctness. Both latency and quality must be checked before a production rollout.

## Next step

Recheck the most promising setting on a larger frozen feed and multiple profiles, with independently assessed relevance and the real semantic-ranking baseline. Preserve an explicit output-quality guard alongside throughput. Full-paper summarization needs a separate memory/context benchmark; these short-output numbers must not be extrapolated to it. Consider a separate compatible vLLM experiment only after this baseline and workload are fixed; this run does not compare inference engines.

Server results: `/data/SFT_demo/Oct/results/qwen_abstract_batching_20261031/` and `/data/SFT_demo/Oct/results/qwen_abstract_batching_warm_20261031/`.
