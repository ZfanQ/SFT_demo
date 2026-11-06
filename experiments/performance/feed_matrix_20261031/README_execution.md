# Expanded Medical Feed Concurrency Experiment

Server root: `/data/SFT_demo/Oct/results/feed_matrix_20261031/`.

## Scope

200 frozen author abstracts × three synthetic interest profiles × concurrency 2/4/8. One request scores one paper for one profile. Each complete model has nine 200-request rounds: 1,800 measured calls, with 5,400 across three models. This measures abstract relevance inference, not full-paper summarization or multiple abstracts packed into one prompt.

The Qwen3-8B matrix was completed and independently verified before the upgrades. Common prompts, article order, 4,096-token slot context, 96-token output cap, seed 42, temperature 0 and thinking-off settings are frozen in `dataset.json`. Source templates/tokenizers differ across models. Each round starts a private service and performs synthetic real-request warmup, excluded from measurement. Partial attempts and probes remain excluded from accepted aggregates.

## Successful-path model labels

| Folder | Checkpoint | Backend |
| --- | --- | --- |
| `qwen3_8b/` | existing `qwen3:8b`, Q4_K_M | Ollama 0.34.4 |
| `qwen35_9b_llamacpp/` | `qwen3.5:9b-q4_K_M` | bundled standalone llama.cpp, official pinned HF template/tokenizer |
| `gemma4_12b_llamacpp/` | `gemma4:12b-it-q4_K_M` | bundled standalone llama.cpp, embedded GGUF template/tokenizer |

Upgraded aliases are `study-qwen35-9b-q4:20261031` and `study-gemma4-12b-q4:20261031`. Alias parameters normalize effective presence/repetition penalties and top-k/top-p/min-p to the old Qwen configuration; the source weights remain unchanged. Exact source references, digests and inherited settings are retained in model-setup JSONs.

`qwen35_9b/` preserves the original Ollama scheduler restriction to one slot; `gemma4_12b/` preserves stalled Ollama empty-input initialization. Both have zero accepted timed rounds. Probe folders preserve bounded compatibility checks and their failures. Read `compatibility_notes_en.md` before comparing backends. The new Gemma Q4_K_M inference configuration is separate from the teammate's historical private HF NF4 summary configuration.

## Artifact map

- `report_en.md`: English results, latency/throughput tradeoffs, score stability, limitations and next steps. It explicitly marks incomplete model coverage until all three are verified.
- `throughput_latency.png`, `.pdf`, `.svg` and `plot_metadata.json`: final exported figure and plotting provenance, generated only for complete coverage.
- `dataset.json`: exact 200 input texts, hashes, 600 paper/profile prompts and common options.
- Per-model `protocol.json`, `status.json`, `analysis.json`, `source_integrity.json`: configuration, completion, independently recalculated measurements and original-file integrity.
- Each accepted round retains `accepted.json` pointing to its immutable attempt folder with raw responses, server log, warmup responses, GPU samples, residency and renderer/tokenizer checks.
- Direct-backend `backend_provenance.json` and `driver_source.py`: actual binary/checkpoint/driver identity. Gemma additionally preserves `round_helper_source.py`.
- `audit_summary.json`: final cross-model 5,400-request and non-overlapping-round verification.
- `server_final_checks.json`: final original-file hashes, private-port shutdown, shared-service health, checkpoint hashes and sft group access.
- `source/` and `script_hashes.json`: pipeline/report/audit snapshots. Qwen3.5's exact earlier execution source remains in its model folder; later Gemma helper hooks do not change that provenance.

## Execution and validation

The final durable continuation is `/data/SFT_demo/Oct/scripts/continue_feed_matrix_gemma_20261031.py`. It independently verifies both completed Qwen matrices, requires the passed Gemma adapter smoke test, runs the native Gemma matrix and audits it. `pipeline.log` and `pipeline_status.json` record progress; successful terminal phase is `all_models_verified` with 5,400 timed calls. Earlier controllers have exited; do not launch them together.

An exclusive root lock prevents concurrent matrix processes. Private benchmark port is 11437, temporary model-download port 11438. Shared Ollama 11434, its binary and scheduler restrictions are preserved. No teammate summaries or author abstracts are changed. New experiment artifacts are shared with sft as directories 2775 and files 0664 after completion.

From this repository, after copying all complete folders and exact driver snapshots:

```bash
python3 tools/verify_feed_matrix_bundle.py --root docs/feed_matrix_20261031
python3 tools/plot_feed_matrix.py --root docs/feed_matrix_20261031
python3 tools/report_feed_matrix.py --root docs/feed_matrix_20261031
```

Plotting requires Matplotlib; inference and audits otherwise use the existing server environment and standard-library orchestration. Qwen3.5 additionally uses its recorded official HF tokenizer assets. Restore any exact old driver into an isolated script directory with the matching base script for historical replay; do not replace a helper used by an active run.

There are no independent relevance gold labels. Agreement, threshold flips and tied-rank correlation measure stability, not correctness. A throughput winner is an operating-point candidate, not a proven optimum. No Strata migration, production deployment or recurring automation is part of this experiment.
