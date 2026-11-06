# GPU24 full-text summarization pilot — 2026-09-28

## Setup

Five papers (`paper_001`–`paper_005`) were summarized from extracted PDF full text on GPU24. Both models used the same source papers, teacher-generated references, summary prompt, and evaluation pipeline. Ollama served quantized Qwen3 models with thinking disabled, temperature 0, and seed 42. The pipeline selected context sizes up to 32,768 tokens; `paper_003` required 32,768.

These are **untuned baseline models**, evaluated on a small five-paper pilot. Scores are mean F1 against the references; they do not establish factual correctness.

## Results

| Model | Papers scored | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B (`qwen3:8b`) | 5/5 | 0.4792 | 0.1674 | 0.2988 | **0.8845** |
| Qwen3-14B (`qwen3:14b`) | 5/5 | **0.5032** | **0.1808** | **0.3065** | 0.8797 |

The 14B model scored higher on all three ROUGE measures; the 8B model scored higher on BERTScore. With five papers, these differences are descriptive rather than a reliable estimate of general performance.

## Per-paper scores

| Paper | Model | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore F1 | Generated words | Target words |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 001 | 8B | 0.5868 | 0.2032 | 0.4164 | 0.9030 | 152 | 137 |
| 001 | 14B | 0.5915 | 0.2057 | 0.3732 | 0.8970 | 121 | 137 |
| 002 | 8B | 0.4267 | 0.1654 | 0.2725 | 0.8797 | 221 | 133 |
| 002 | 14B | 0.5054 | 0.2054 | 0.3280 | 0.8844 | 201 | 133 |
| 003 | 8B | 0.4048 | 0.1094 | 0.2296 | 0.8579 | 171 | 136 |
| 003 | 14B | 0.4396 | 0.1246 | 0.2291 | 0.8607 | 153 | 136 |
| 004 | 8B | 0.5563 | 0.2200 | 0.3179 | 0.9018 | 131 | 132 |
| 004 | 14B | 0.5402 | 0.2071 | 0.3408 | 0.8845 | 136 | 132 |
| 005 | 8B | 0.4214 | 0.1392 | 0.2579 | 0.8800 | 169 | 132 |
| 005 | 14B | 0.4392 | 0.1612 | 0.2611 | 0.8719 | 186 | 132 |

`paper_002` was manually checked against the source and judged factually accurate, but both outputs exceeded the target length substantially. A systematic blinded factuality review has not yet been completed.

## Local records

- 8B result and summary snapshot: `.cache/baselines/qwen3-8b/`
- 14B result: `.cache/experiments/qwen3-14b/outputs/results.md`
- 14B summaries: `.cache/experiments/qwen3-14b/references/paper_XXX_qwen.txt`

These paths are local to GPU24 and are not committed to Git. The 14B experiment used a separate reference directory so its generated summaries did not overwrite the tracked 8B summaries. The repository's earlier README result was produced in a different run and is retained separately.

## Next steps

Expand the fixed test set, review factuality and length compliance across papers, then compare the selected baseline with a fine-tuned Qwen3-8B on the same held-out inputs.
