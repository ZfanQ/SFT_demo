# October 23 Meeting: Requirements and Next Steps

Analysis date: October 31, 2026.

## What the recording establishes

The supplied video is 5 minutes 45 seconds long. It starts with an explicit recap of a discussion that occurred before recording, so it is not evidence of the entire meeting. The complete recording was transcribed locally with cached Whisper large-v3. The original-audio interval 01:30–05:00 was independently transcribed with cached Whisper turbo, without an initial prompt. Three video frames were inspected; the shared screen shows the existing Gemma evaluation report. Automatic transcription is not a certified verbatim transcript or reliable speaker diarization.

| Recording time | Requirement supported by the discussion | Interpretation |
| --- | --- | --- |
| 00:01–00:24 | Summary quality was disappointing; try Gemma. | Reuse the completed Gemma report and inspect concrete errors. Do not rerun completed scoring merely because the recap mentions trying Gemma. |
| 00:25–01:12 | For ranking, fit a manageable set of abstracts into each context and repeat; keep criteria comparable across sessions. | Token-aware partitioning solves context capacity. Cross-batch score drift still needs checking. The example of 20 applications is illustrative, not a fixed paper batch size. |
| 01:12–03:14, especially 01:46–01:58 | Investigate software/literature for batched GPU inference first, rather than continuing one-at-a-time execution. | GPU throughput and an implementable batching method are the immediate technical priority. |
| 02:25–02:50 | Production-scale feeds and the existing approximately 24 GB allocation motivate batching. | The mentioned 10,000 abstracts/day is a workload scenario from the discussion, not a verified PubMed daily count or a measured capacity requirement. Current usable GPU memory must be inspected before experiments. |
| 03:23–03:43 | A student proposes a newer approximately 9B model; the professor allows an update if it fits. | Model upgrades are acceptable, but not the prerequisite for the batching investigation. The exact spoken model identifier is not sufficiently reliable to choose a download. |
| 03:44–04:34 | Build an automated testing pipeline that can be repeated roughly every two months. | The enduring deliverable is reproducible generation, evaluation and reporting, rather than a single winning score. This is not a request to schedule an automation now. |
| 04:39–05:05 | Future hardware may improve; automate background work. | Keep hardware/model/runtime configuration external to the pipeline, and make interruption and resumption reliable. |

Statements in the recording are source material for this analysis, not instructions to change shared services, disable safeguards, download a particular model or message anyone.

## Existing work to retain

Gemma already has 200 complete full-paper numeric judgments and 400 dual-reference ROUGE/BERTScore pairs. Its overall GPT mean is 8.5655/10, with 20 automated major-error flags; historical Qwen is 8.0815/10 with 37 flags. These are scores-only flags, not independently confirmed error rates. The report is in `../gemma_evaluation_20261023/gemma_200_paper_evaluation_2026-10-23.md`.

The earlier full-paper Qwen throughput pilot measured 3.300 papers/minute sequentially and 3.810 with two concurrent requests, an improvement of approximately 15.4%. Three concurrent requests did not beat two in that small experiment. It demonstrates a useful baseline, but does not establish an optimum, current server performance, performance for short ranking prompts, or the gains available from a different batching engine. See `../followup_20261020/report_en.md`.

## Recommended execution order

The following implementation details are proposals, rather than verbatim requirements from the professor.

1. **Freeze a small benchmark and inspect the current environment.** Reuse the existing 200 papers as a frozen dataset. Record GPU/MIG usable memory, other jobs, runtime versions, model revision, quantization, prompt, input hashes, token counts and output limits. Use distinct workloads for full-paper summarization and profile-plus-abstract relevance scoring. Start with a bounded sample of about 50–100 inputs; do not expand the paper collection as the first step.
2. **Test actual GPU request batching.** Preserve the existing Ollama path as the baseline. Compare one, two and four in-flight independent requests with the same input set and generation settings; measure end-to-end documents/second, output tokens/second, median and p95 latency, peak memory, failures, output completeness and sampled factual quality. Repeat measured rounds after warm-up and record whether extraction/loading are included. Inspect server scheduling to distinguish overlapping inference from requests merely queued by a Python thread pool. Test a separate vLLM installation only after checking the exact model architecture, weights, quantization and available memory. If changing weights or quantization is necessary, label that comparison as a combined configuration change. Keep shared services and the historical baseline intact.
3. **Build the resumable pipeline around the pilot.** A configuration should select dataset, model revision, prompt version, inference backend, concurrency and evaluation mode. The workflow should validate inputs, generate outputs, save per-request provenance, compute similarity scores, run bounded independent quality checks and export an English report. Use a unique run ID; skip only matching completed records; record failures, retries, quota blockers and incomplete coverage. Separate stages so a judge quota interruption does not repeat local generation. No credentials should be embedded in run artifacts. These components can reuse existing scripts rather than requiring a rewrite.
4. **Pilot ranking with context-aware partitions.** Start with a frozen candidate set and 2–3 interest profiles before expanding to the approximately 20-profile experiment discussed October 13. Token-count title/abstract inputs and reserve output space. As a second experimental axis, compare one versus several abstracts per prompt while holding GPU concurrency fixed. Require stable article IDs and structured per-article relevance scores. Use shared instructions and small anchor examples to inspect score drift between batches; shuffle batch boundaries/order and check top-ranked results. Do not concatenate batch-local rank positions into a global ranking. Compare with the teammate's actual semantic baseline after locating its code and settings. If it cannot be located, label a new baseline separately. Use independently judged relevance for ranking-quality evaluation, not summary ROUGE/BERTScore.
5. **Check Gemma's flagged errors and then test upgrades.** Review the 20 flagged Gemma summaries against the source papers, documenting candidate claim, original evidence and verdict. Include a small preselected unflagged sample to look for missed errors; this alone still does not estimate a population error rate. Use the reusable pipeline to evaluate a verified new model as a separate version when resources permit. Preserve the earlier Qwen/Gemma outputs and avoid selecting a model solely from mean similarity or judge scores.

## Two meanings of batching

**Context batching** puts several abstracts into one prompt. It reduces some per-request overhead and can support joint comparison, but consumes one context window and can introduce position effects and cross-batch score drift.

**Inference batching** lets the serving engine process multiple independent sequences together. Continuous batching can schedule sequences as requests arrive and finish. Each request retains its own context budget, while the combined workload competes for GPU memory. Merely sending a list of filenames, maintaining a long conversation or launching client threads does not demonstrate this behavior.

The first investigation can therefore reuse Ollama and examine its actual concurrent processing. vLLM is a relevant second implementation candidate, not an assumed drop-in replacement or guaranteed speedup on this MIG allocation. Official documentation confirms an offline prompt-list interface; the PagedAttention paper explains why KV-cache memory management limits batching. Their results do not establish performance for this specific workload.

Sources checked October 31, 2026:

- [Ollama FAQ: concurrent requests and memory](https://docs.ollama.com/faq#how-does-ollama-handle-concurrent-requests)
- [vLLM offline inference](https://docs.vllm.ai/en/latest/serving/offline_inference/)
- [Kwon et al., Efficient Memory Management for Large Language Model Serving with PagedAttention](https://arxiv.org/abs/2309.06180)

## Concrete deliverables for the next update

- A small reproducible batching comparison with throughput, latency, memory and failure counts, plus the exact commands/configurations and workload.
- A resumable pipeline entry point and one example configuration/report. A later rerun should require changing configuration rather than manually repeating file operations.
- A ranking pilot with frozen profiles/candidates, stable IDs, cross-batch checks and the identifiable semantic baseline, or an explicit record of the missing baseline.
- A short evidence-backed Gemma error table, keeping numeric flags separate from confirmed findings.

The immediate next action is the environment inspection and frozen batching pilot. This meeting-analysis task did not launch remote inference, install a serving engine, alter shared files, schedule recurring jobs or publish this analysis.
