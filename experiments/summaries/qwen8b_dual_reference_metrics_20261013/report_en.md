# Qwen3-8B: 200-Paper ROUGE and BERTScore Evaluation

Evaluation date: October 13, 2026.

## Scope

The same 200 saved Qwen3-8B summaries were evaluated against two reference sets: the original author abstracts and an existing snapshot of 200 GPT reference summaries. This produced 400 candidate–reference pairs. Candidate summaries were held fixed across both evaluations.

This run calculated text-similarity metrics only. It did not generate or rewrite summaries or conduct a GPT quality assessment.

## Results: all 200 papers

Each value is the unweighted arithmetic mean of per-paper F1 scores on a 0–1 scale. BERTScore values are not rescaled against a baseline.

| Reference | Papers | ROUGE-1 F1 | ROUGE-2 F1 | ROUGE-L F1 | BERTScore F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original author abstract | 200 | 0.6310 | 0.3844 | 0.4418 | 0.9033 |
| GPT reference summary | 200 | 0.4702 | 0.1384 | 0.2552 | 0.8713 |

Qwen summaries were more similar to the author abstracts than to the GPT references under these metrics. This comparison concerns reference-text similarity; it does not establish that either reference is more factually accurate or rank Qwen against other models.

## Matched subset without BERTScore truncation

Eleven author abstracts exceeded the RoBERTa tokenizer limit of 512 tokens, including special tokens. Standard BERTScore truncation affected those author-reference pairs. ROUGE used the complete texts for every paper. No Qwen or GPT summary exceeded the tokenizer limit.

Affected paper IDs: 049, 061, 095, 130, 141, 147, 153, 154, 173, 190, and 192.

For a comparison where both references fit entirely within the BERTScore input limit, the following table uses the same remaining 189 papers for both reference sets.

| Reference | Matched papers | ROUGE-1 F1 | ROUGE-2 F1 | ROUGE-L F1 | BERTScore F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original author abstract | 189 | 0.6337 | 0.3860 | 0.4437 | 0.9042 |
| GPT reference summary | 189 | 0.4693 | 0.1376 | 0.2536 | 0.8712 |

## Evaluation protocol

| Setting | Value |
| --- | --- |
| ROUGE variants | ROUGE-1, ROUGE-2, ROUGE-L |
| ROUGE stemming | Enabled |
| BERTScore encoder | roberta-large |
| Encoder layer | 17 |
| Encoder revision | `722cf37b1afa9454edce342e7895e588b6ff1d59` |
| Language | English |
| IDF weighting | Disabled |
| Baseline rescaling | Disabled |
| Tokenizer | Slow tokenizer |
| BERTScore input limit | 512 tokens, including special tokens |
| Device / batch size | CPU / 1 |
| Aggregation | Equal weight per paper; no corpus concatenation |

Both candidates and references were normalized by joining whitespace-separated tokens with single spaces. Original author-abstract headings and trial-registration information were retained. The original abstracts were not compressed to a word limit. Reference word counts did not control candidate generation in this evaluation.

The GPT reference set was frozen at scoring time. It contains 175 summaries generated with GPT-6.1 Sol and 25 preserved teammate summaries whose exact original model and prompt were not independently verified. These references should not be described as 200 outputs from one uniform generation protocol. A subsequently regenerated reference set requires a separate evaluation version.

## Reproducibility and validation

| Package | Version |
| --- | --- |
| torch | 2.14.0 |
| transformers | 5.17.0 |
| bert-score | 0.3.13 |
| rouge-score | 0.1.2 |
| huggingface-hub | 1.33.0 |

Recorded BERTScore configuration hash: `roberta-large_L17_no-idf_version=0.3.12(hug_trans=5.17.0)`.

Input snapshot SHA-256: `1a60c44d870505ffa1e2faee15a59b976353d36efd89c108cff7c852787fd234`.

Scoring script SHA-256: `b7e1fdc1d7c1b616a74b35d9678b8e530c556f129ae83b2341310053486fdb5a`.

Validation confirmed 400 unique score rows, identical candidate hashes across the two reference sets, finite metric values, and independently recomputed aggregate means. All 600 original input files matched their frozen snapshot hashes at the end of scoring. All 11 BERTScore truncation cases were explicitly identified.

ROUGE and BERTScore measure lexical overlap and contextual semantic similarity. They do not independently verify claims against the complete scientific paper.
