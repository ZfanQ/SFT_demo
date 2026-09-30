# Paper Summarization: Baseline Model Comparison

## Overview

We compare four open-weight models on the full text of the same five scientific papers. The goal is to establish baseline performance before fine-tuning.

All four models completed summarization and evaluation for all five papers.

## Evaluation Setup

| Item | Description |
| --- | --- |
| Hardware | H100 MIG 24 GB |
| Papers | `paper_001`–`paper_005` |
| Input | Full paper text |
| Output | English summary |
| Length target | Word count of the corresponding reference summary |
| References | Teacher-generated summaries |
| Metrics | ROUGE-1, ROUGE-2, ROUGE-L, BERTScore |

Models receive the reference word count as a length target, but never the reference summary text.

All metrics are F1 scores on a 0–1 scale. Results below are averages across the five papers. Higher scores indicate greater similarity to the references.

## Average Results

| Model | Papers evaluated | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B | 5/5 | 0.4792 | 0.1674 | 0.2988 | **0.8845** |
| Qwen3-14B | 5/5 | **0.5032** | 0.1808 | 0.3065 | 0.8797 |
| Gemma 4 12B IT | 5/5 | 0.4880 | **0.1868** | **0.3208** | 0.8825 |
| Llama 3.1 8B Instruct | 5/5 | 0.4125 | 0.1306 | 0.2609 | 0.8704 |

Bold values indicate the highest score in each metric column.

## What the Metrics Measure

| Metric | Interpretation |
| --- | --- |
| ROUGE-1 | Overlap of individual words |
| ROUGE-2 | Overlap of consecutive word pairs |
| ROUGE-L | Matching word sequences in the same order |
| BERTScore | Similarity of words in their semantic context |

These metrics compare generated summaries with reference summaries. They do not directly measure factual correctness.

## Summary Length

Each cell shows **generated summary words / reference summary words**.

| Paper | Qwen3-8B | Qwen3-14B | Gemma 4 12B IT | Llama 3.1 8B Instruct |
| --- | ---: | ---: | ---: | ---: |
| paper_001 | 152 / 137 | 121 / 137 | 128 / 137 | 155 / 137 |
| paper_002 | 221 / 133 | 201 / 133 | 123 / 133 | 153 / 133 |
| paper_003 | 171 / 136 | 153 / 136 | 128 / 136 | 180 / 136 |
| paper_004 | 131 / 132 | 136 / 132 | 117 / 132 | 147 / 132 |
| paper_005 | 169 / 132 | 186 / 132 | 126 / 132 | 163 / 132 |

Gemma summaries are slightly shorter than the references for all five papers. The other models exceed the reference length on several papers.

## Main Findings

- Qwen3-14B has the highest ROUGE-1 score.
- Gemma has the highest ROUGE-2 and ROUGE-L scores.
- Qwen3-8B has the highest BERTScore.
- Llama has the lowest average score across all four metrics.
- No model leads on every metric.

## Model Highlights

| Model | Main strength in this comparison | Supporting result |
| --- | --- | --- |
| **Qwen3-8B** | **Highest semantic similarity score** | Best BERTScore (**0.8845**), with fewer parameters than the two 12B/14B models |
| **Qwen3-14B** | **Highest individual-word overlap** | Best ROUGE-1 (**0.5032**) |
| **Gemma 4 12B IT** | **Highest phrase and sequence overlap; summaries close to the target length** | Best ROUGE-2 (**0.1868**) and ROUGE-L (**0.3208**); all five summaries slightly below the reference word count |
| **Llama 3.1 8B Instruct** | **Additional baseline from a different model family** | Completed all five papers, but showed no leading score in this comparison |

**Qwen3-8B and Gemma are promising candidates for further evaluation:** Qwen3-8B combines a smaller parameter count with the highest BERTScore, while Gemma leads on two ROUGE metrics and produces summaries close to the requested length.

These strengths are based on five papers. Factual accuracy, readability, and measured inference cost still need to be evaluated before selecting a model for fine-tuning.

## Run Notes and Limitations

- Only five papers are included, so the findings are preliminary.
- Qwen runs through Ollama. Gemma and Llama run through Hugging Face Transformers. Compression methods and generation settings differ, which limits direct comparability.
- The teacher model and version used to generate the references have not been confirmed.
- Factual accuracy and readability have not yet been assessed.
- Inference speed and memory use are not reported in this comparison.

## Next Steps

1. Review summaries against the original papers for factual errors and missing key findings.
2. Evaluate relevance, readability, and conciseness using a shared rubric.
3. Record inference time and GPU memory use.
4. Expand the test set before selecting a model for fine-tuning.

## Files and Sources

- [Qwen baseline results](../docs/gpu24-qwen-baselines-2026-09-28.md)
- [Earlier local Qwen experiment](README.md)
- [Qwen evaluation script](qwen_eval.py)
- [Gemma / Llama evaluation guide](README_Gemma_Llama.md)
- [Gemma / Llama evaluation script](Gemma_Llama_eval.py)

Gemma and Llama scores were taken from the completed server results at `local_test/outputs/gemma_llama_nf4/README.md`.

The earlier local Qwen experiment is a separate run and is not included in the comparison table above.