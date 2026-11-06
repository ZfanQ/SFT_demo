# Qwen / Gemma / Llama Paper Summarization Results

This report combines full-text summarization results for the same five papers (`paper_001`–`paper_005`). The main comparison uses the Qwen GPU24 runs from September 28, 2026, and the completed Gemma / Llama results supplied by the user from September 30, 2026.

R1, R2, and RL denote ROUGE-1, ROUGE-2, and ROUGE-L F1, respectively. BERTScore also denotes F1. All scores are on a 0–1 scale; each aggregate is the arithmetic mean across five papers. Aggregate values are retained from the original reports rather than recalculated from rounded per-paper scores.

## Mean Scores Across Five Papers

| Model | Run | Scored | R1 | R2 | RL | BERTScore |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B (Ollama, quantized) | GPU24 · 2026-09-28 | 5/5 | 0.4792 | 0.1674 | 0.2988 | **0.8845** |
| Qwen3-14B (Ollama, quantized) | GPU24 · 2026-09-28 | 5/5 | **0.5032** | 0.1808 | 0.3065 | 0.8797 |
| Gemma 4 12B IT (4-bit NF4) | H100 MIG 24 GB · 2026-09-30 | 5/5 | 0.4880 | **0.1868** | **0.3208** | 0.8825 |
| Llama 3.1 8B Instruct (4-bit NF4) | H100 MIG 24 GB · 2026-09-30 | 5/5 | 0.4125 | 0.1306 | 0.2609 | 0.8704 |

Bold values indicate the highest score in each metric column. Qwen3-14B has the highest R1, Gemma has the highest R2 and RL, and Qwen3-8B has the highest BERTScore. These are descriptive comparisons on five samples; they do not establish general model superiority or factual accuracy.

## Per-Paper Scores

Gemma and Llama use NF4 quantization in the table below. Both Qwen models use the GPU24 runs. `Words / target` gives the generated summary word count followed by the reference summary word count.

| Paper | Model | R1 | R2 | RL | BERTScore | Words / target |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| paper_001 | Qwen3-8B | 0.5868 | 0.2032 | 0.4164 | 0.9030 | 152 / 137 |
| paper_001 | Qwen3-14B | 0.5915 | 0.2057 | 0.3732 | 0.8970 | 121 / 137 |
| paper_001 | Gemma 4 12B IT | 0.5616 | 0.1931 | 0.3699 | 0.8933 | 128 / 137 |
| paper_001 | Llama 3.1 8B Instruct | 0.4317 | 0.1342 | 0.2603 | 0.8801 | 155 / 137 |
| paper_002 | Qwen3-8B | 0.4267 | 0.1654 | 0.2725 | 0.8797 | 221 / 133 |
| paper_002 | Qwen3-14B | 0.5054 | 0.2054 | 0.3280 | 0.8844 | 201 / 133 |
| paper_002 | Gemma 4 12B IT | 0.5245 | 0.2324 | 0.3776 | 0.8914 | 123 / 133 |
| paper_002 | Llama 3.1 8B Instruct | 0.3653 | 0.1121 | 0.2167 | 0.8605 | 153 / 133 |
| paper_003 | Qwen3-8B | 0.4048 | 0.1094 | 0.2296 | 0.8579 | 171 / 136 |
| paper_003 | Qwen3-14B | 0.4396 | 0.1246 | 0.2291 | 0.8607 | 153 / 136 |
| paper_003 | Gemma 4 12B IT | 0.3930 | 0.1343 | 0.2526 | 0.8596 | 128 / 136 |
| paper_003 | Llama 3.1 8B Instruct | 0.3710 | 0.1283 | 0.2551 | 0.8531 | 180 / 136 |
| paper_004 | Qwen3-8B | 0.5563 | 0.2200 | 0.3179 | 0.9018 | 131 / 132 |
| paper_004 | Qwen3-14B | 0.5402 | 0.2071 | 0.3408 | 0.8845 | 136 / 132 |
| paper_004 | Gemma 4 12B IT | 0.5105 | 0.2183 | 0.2937 | 0.8949 | 117 / 132 |
| paper_004 | Llama 3.1 8B Instruct | 0.5161 | 0.1753 | 0.3226 | 0.8823 | 147 / 132 |
| paper_005 | Qwen3-8B | 0.4214 | 0.1392 | 0.2579 | 0.8800 | 169 / 132 |
| paper_005 | Qwen3-14B | 0.4392 | 0.1612 | 0.2611 | 0.8719 | 186 / 132 |
| paper_005 | Gemma 4 12B IT | 0.4502 | 0.1561 | 0.3100 | 0.8730 | 126 / 132 |
| paper_005 | Llama 3.1 8B Instruct | 0.3782 | 0.1032 | 0.2500 | 0.8762 | 163 / 132 |

## Evaluation Protocol and Run Differences

- Gemma / Llama reuse the full-text extraction procedure and English summary prompts from `qwen_eval.py`. Only the reference word count is provided as a length target; reference text is never supplied to the summary generator.
- ROUGE uses stemming. Gemma / Llama BERTScore uses `roberta-large`, layer 17, `idf=False`, no baseline rescaling, the slow tokenizer, CUDA, and batch size 1. The historical Qwen script uses the same metric settings but defaults to CPU for BERTScore; the GPU24 report does not separately document its actual scoring device.
- The Qwen GPU24 runs use quantized Ollama models with thinking disabled, temperature 0, seed 42, and a context cap of 32,768 tokens. The original report does not specify the quantization format, so these runs should not be described as NF4.
- Gemma / Llama use Hugging Face Transformers, NF4 with double quantization, BF16 computation, SDPA, greedy decoding, seed 42, and a maximum of 768 generated tokens. Gemma thinking is disabled. The context cap is 40,960 tokens, with an additional margin of 256 tokens and a configured summary length tolerance of 10%.
- Gemma / Llama run on an H100 `MIG 1g.24gb` partition. NF4 compresses supported Linear layers; some weights retain floating-point precision. The BERTScore encoder is not quantized.
- Full paper inputs are not truncated. After an out-of-memory failure, Gemma completed `paper_003` using **chunked prefill with 2,048 tokens per chunk**. The other nine summaries retain their original unchunked results. Chunked prefill maintains one continuing KV cache and generates a single summary after processing the entire input; it does not generate and merge separate chunk summaries.
- Chunking can introduce floating-point differences. This report therefore combines different prefill settings and is not a uniform chunked rerun across all models and papers. Previous experiment configurations, state backups, and per-paper provenance are retained in the server records.
- References are teacher-generated; the teacher model and version are unknown. Differences in inference frameworks, quantization methods, and summary lengths affect comparability. ROUGE and BERTScore measure similarity to references rather than factual correctness.

### Gemma / Llama Model and Prefill Settings

| Model | Checkpoint | Weights | Compute | Prefill |
| --- | --- | --- | --- | --- |
| Gemma 4 12B IT | `google/gemma-4-12B-it` | 4-bit NF4 + double quantization | BF16 | paper_003: 2048; all others: full |
| Llama 3.1 8B Instruct | `meta-llama/Llama-3.1-8B-Instruct` | 4-bit NF4 + double quantization | BF16 | full for all five papers |

The requested revision was `main`. Resolved model commits, package versions, input hashes, raw responses, and detailed configurations are recorded in the server's `run_state.json` and `raw/` directory. This report consolidates the supplied results without rerunning models or metrics, and the server's raw files have not been independently verified for this consolidation.

## Earlier Local Qwen Results (Separate Run)

The repository's original `local_test/README.md` records a separate local Qwen3-8B run. Its results differ from the GPU24 run and are retained separately; the two runs are not averaged or combined into a single model entry.

| Model | Run | Scored | R1 | R2 | RL | BERTScore |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B (`qwen3:8b`) | Earlier local Ollama run | 5/5 | 0.4918 | 0.1700 | 0.2771 | 0.8817 |

The earlier README does not provide per-paper scores. Per-paper scores from GPU24 are not used as substitutes for that run.

## Sources

- Qwen GPU24 aggregate scores, per-paper scores, and word counts: [GPU24 evaluation report, September 28, 2026](../docs/gpu24-qwen-baselines-2026-09-28.md).
- Earlier local Qwen3-8B aggregate scores: [Original local_test README](README.md).
- Gemma / Llama: the completed results README supplied by the user in this conversation, with every entry marked `scored`. The report is located on the server at `/home/zifan/projects/SFT_demo/local_test/outputs/gemma_llama_nf4/README.md`.
- Implementations: [Qwen evaluation script](qwen_eval.py) and [Gemma / Llama evaluation script](Gemma_Llama_eval.py).
