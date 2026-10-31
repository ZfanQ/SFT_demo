# Upgraded Model Backend Compatibility Findings

Date: October 31, 2026.

The Qwen3-8B 200-paper, three-profile matrix completed and passed independent verification before any upgraded model inference was attempted.

## Original Ollama configuration

The pinned Qwen3.5-9B Q4_K_M checkpoint downloaded successfully and ran valid warmup requests on GPU. However, Ollama 0.34.4 logged `model architecture does not currently support parallel requests` for `qwen35`. The actual launch used `-np 1`, `n_seq_max` was 1, and the scheduler reported `runner.parallel=1` despite requested parallelism 2. The runner stopped before measured requests. This is a scheduler compatibility result, not a measured model-throughput result or an out-of-memory failure.

The matching source is [Ollama v0.34.4 server/sched.go](https://github.com/ollama/ollama/blob/v0.34.4/server/sched.go). `Scheduler.load` explicitly replaces the requested parallel count with 1 for a list including `qwen35`. The corresponding [upstream proposal #17144](https://github.com/ollama/ollama/pull/17144) was still open when checked; a blind release upgrade was therefore not assumed to solve the issue.

The failed preflight remains under server `qwen35_9b/oncology_p2/attempt01/`. There are zero accepted timed rounds for that native Ollama configuration. The shared service, installed Ollama binary and blocklist were not modified.

## Separate llama.cpp backend

A separate text-only driver uses the already installed llama.cpp server directly. It reads the same content-addressed Qwen3.5 checkpoint, verifies its SHA-256, applies the pinned official HF chat template with thinking disabled and confirms exact token-ID equality with the server's GGUF tokenizer. It preserves native responses alongside normalized timing/output fields for the common audit. This backend has a different renderer and frontend from the Ollama runs and must be labeled as such in model comparisons.

The first direct probe did not discover CUDA. Its CPU startup was rejected before timing. Reading the loader implementation established that the bundled out-of-tree CUDA plugin requires `GGML_BACKEND_PATH`, in addition to dynamic-library paths. An explicit device-list probe then found the H100 MIG device. References: [Ollama launcher](https://github.com/ollama/ollama/blob/main/llm/llama_server.go), [llama.cpp backend loader](https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-backend-reg.cpp).

The second probe loaded all 33/33 layers on GPU with two slots and a 4,096-token slot context. A validator initially expected the older log name `n_ctx_per_seq`; this build prints `n_ctx_seq`. The parser was corrected to recognize both names while retaining the exact context requirement. No model parameters were changed to make this check pass.

The third probe completed eight requests, all with valid IDs and scores. It confirmed 33/33 GPU-offloaded layers, two sequences, 4,096 tokens per slot and exact official/GGUF tokenizer parity. It is a compatibility smoke test, excluded from the full matrix throughput total.

The full direct-backend run uses label `qwen35_9b_llamacpp`; its `backend_provenance.json` records the server binary version/hash, checkpoint hash, official tokenizer revision and driver hash. It remains a bounded experiment, not a claim of universal backend safety or production ranking quality. Each 2/4/8 measured round must still pass independent slot, response, token-budget and residency checks.

## Preservation

All failed-probe directories and prior sources were retained. No teammate summary or original abstract was edited. The Gemma checkpoint was prepared outside timed rounds. Its later Ollama Q4_K_M experiment is separate from the teammate's historical HF NF4 summary run.

## Gemma initialization and separate native matrix

The original Ollama Gemma configuration stopped during empty-input engine initialization with a request timeout, before any timed requests. The last startup log line was `common_init_: warming up the model with an empty run - please wait ...`. That failed attempt remains under `gemma4_12b/oncology_p2/attempt01/` and contributes no throughput measurements.

A bounded eight-request text-only probe succeeded with the same Gemma Q4_K_M checkpoint and the existing standalone llama.cpp server, explicit CUDA discovery, `--no-warmup`, `--jinja`, `--reasoning off` and `--reasoning-budget 0`. All 49/49 model layers were offloaded; two real execution slots and 4,096 tokens per slot were verified. A subsequent adapter smoke test again passed eight requests, including preserved-input and context-budget checks. Both smoke tests are excluded from the measured matrix.

The full configuration is separately labeled `gemma4_12b_llamacpp`. It uses the embedded GGUF chat template/tokenizer and native structured chat API, preserving the complete native responses. All 200 user/system inputs are checked for literal preservation and context budget before each measured round. No independently loaded official-HF tokenizer parity check was established for Gemma. The common synthetic real-request warmup still runs at each concurrency and is excluded from timing; only the backend's default empty-input startup warmup is skipped.

This workaround changes frontend/text-only initialization and disables the empty-input warmup together. The exact kernel cause of the Ollama initialization stall has not been isolated, so the successful probe must not be presented as proof of that cause. The original service and installed binaries remain unchanged. This experiment uses accessible Q4_K_M weights and is separate from the teammate's historical private HF NF4 summary configuration.
