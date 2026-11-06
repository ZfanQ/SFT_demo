# Expanded Medical Feed Batching Implementation Plan

**Goal:** Evaluate all 200 existing abstracts under three fixed interest profiles at 2/4/8 concurrent requests, establish Qwen3-8B results, then evaluate Qwen3.5-9B and Gemma-4-12B.

**Architecture:** One private loopback inference service per measured round: Ollama for 8B and standalone llama.cpp for upgraded models after compatibility checks; shared existing service left unchanged. Immutable prompts, per-round checkpoints and raw responses permit audit and resumption; partial interrupted rounds are retained and excluded from timed aggregates. User has authorized execution in this chat; implement natively without an additional approval handoff.

**Tech stack:** Existing Python 3.12, installed Ollama 0.34.4 initially, local model storage under /data, standard-library HTTP/threading; an isolated newer runtime only if a verified compatibility failure requires it.

## Global constraints

- 200 original abstract files remain unchanged; historical summaries and result directories remain intact.
- Three profiles: oncology, cardiovascular medicine, neuroscience. One independent abstract per request, score 0–3, paper/profile IDs in structured JSON.
- Per-profile Latin order: 2/4/8, 4/8/2, 8/2/4. Each model has 9 complete 200-request rounds (1,800 timed inferences). A complete workload is repeated once per concurrency, not repeatedly sampled as if papers were independent timing runs.
- Fix prompt contents, ordering seed, 4,096 context, 96 output cap, temperature 0 and seed 42; thinking disabled. Record model digest and quantization. Model-specific tokenization/templates remain comparison limitations.
- Representative warmup: 2 × target concurrency, synthetic abstracts with disjoint IDs; warmup excluded, same warmup workload recipe across models.
- Validate full GPU residency and effective runner slot count; stop for invalid outputs, shared-service activity or CPU fallback. Failed configurations are recorded, not silently replaced.
- Qwen3-8B completed and independently verified before adding Qwen3.5-9B; then test Gemma-4-12B via a compatible accessible model. Saved teammate HF Gemma cache is currently private; no permission changes to that directory.
- English report, preserved raw records and sft group read/write access for newly created artifacts. No Strata migration in this experiment.

## Review focus

Input drift must invalidate a resumed run; IDs/JSON/type/range and completion must be checked; actual engine parallelism must be distinguished from requested concurrency; contextual truncation/CPU fallback must not become an unreported performance gain; no relevance gold labels means agreement and rank stability cannot certify quality.

## Tasks

- [x] Implement `tools/benchmark_feed_matrix.py`: immutable dataset preparation, per-model smoke/preflight, private-round orchestration, exact input/output provenance, per-request rows, interruption-safe partial status and server cleanup.
- [x] Run a small schema/slot smoke test, then the complete Qwen3-8B matrix. Keep invalid/supported configurations explicit.
- [x] Implement `tools/analyze_feed_matrix.py`: independently recalculate timings, validate all raw responses/hash sets, report per-profile and combined throughput, latency, memory, ordinal-score disagreement and tied-rank correlation.
- [x] Download compatible pinned Qwen3.5-9B weights only after establishing the first result; smoke-test and run the same matrix. Preserve any incompatibility evidence and use an isolated runtime if necessary.
- [x] Repeat for Gemma-4-12B with its exact backend/quantization labeled separately from prior HF NF4 summaries.
- [x] Recheck source hashes, private service shutdown, result permissions and complete/partial coverage. Save an English comparison report and report observed tradeoffs without claiming a globally optimal concurrency or validated ranking quality.

## Validation

Use targeted local tests for score-schema rejection, immutable-resume rejection and aggregate/rank arithmetic. Real smoke tests verify model-specific backend/schema compatibility; full runs establish timing evidence. Review anomalous labels against supplied abstracts without treating absence from an abstract as a claim about the complete paper.

## Observed backend adjustment

Qwen3-8B completed all 1,800 requests. Ollama 0.34.4 forces qwen35 to one slot; no timed upgraded-model rows were accepted on that path. The same Q4_K_M checkpoint passed an eight-request standalone llama.cpp GPU/tokenizer probe and the full run completed and was independently verified as qwen35_9b_llamacpp. This backend change is explicitly preserved in provenance and comparisons. The shared service and scheduler blocklist remain unchanged.

Completion: all three matrices passed independent audits (27 rounds; 5,400 valid timed requests). Original 200 abstracts and model hashes were rechecked; private ports are closed, shared Ollama is healthy, and new result-tree sft access was verified. The English report and PNG/PDF/SVG figure were generated and visually inspected.
