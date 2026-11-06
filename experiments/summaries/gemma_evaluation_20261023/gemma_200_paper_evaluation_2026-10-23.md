# Gemma: 200-Paper ROUGE, BERTScore and GPT Evaluation

Evaluation date: October 23, 2026. Candidates are the 200 saved `google/gemma-4-12B-it` summaries; no summaries were regenerated or corrected for scoring.

## Findings

Gemma is more similar to the frozen GPT references than the historical Qwen outputs under all four reported metrics; Qwen is more similar to the original author abstracts. These results measure agreement with the chosen reference text, rather than factual correctness. The separate full-paper GPT judge assigned Gemma a mean overall score of **8.5655/10**, compared with **8.0815/10** for the historical Qwen run. This is a descriptive comparison of saved outputs, not an isolated model effect or a human-validated ranking.

Both Gemma evaluations are complete: 400 candidate–reference metric pairs and 200 independent full-paper GPT judgments. The scoring protocol was kept consistent with the corresponding Qwen evaluations. All 400 reference-file hashes match the historical Qwen snapshot.

## Similarity metrics: all 200 papers

Values are unweighted means of per-paper F1 scores. BERTScore is reported without baseline rescaling. Both candidates use exactly the same author abstracts and frozen GPT references.

| Candidate | Reference | Papers | ROUGE-1 F1 | ROUGE-2 F1 | ROUGE-L F1 | BERTScore F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B | Author abstract | 200 | 0.6310 | 0.3844 | 0.4418 | 0.9033 |
| Gemma-4-12B-it | Author abstract | 200 | 0.5483 | 0.2707 | 0.3380 | 0.8882 |
| Qwen3-8B | GPT reference snapshot | 200 | 0.4702 | 0.1384 | 0.2552 | 0.8713 |
| Gemma-4-12B-it | GPT reference snapshot | 200 | 0.4779 | 0.1502 | 0.2739 | 0.8744 |

## Matched subset without BERTScore truncation

Eleven author abstracts exceed the RoBERTa limit of 512 tokens, including special tokens: 049, 061, 095, 130, 141, 147, 153, 154, 173, 190 and 192. Standard BERTScore truncation affects those author-reference pairs; no Gemma or GPT reference summary exceeds this limit. ROUGE always uses complete texts. The following comparison uses the same remaining 189 papers for both references and both candidates.

| Candidate | Reference | Papers | ROUGE-1 F1 | ROUGE-2 F1 | ROUGE-L F1 | BERTScore F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-8B | Author abstract | 189 | 0.6337 | 0.3860 | 0.4437 | 0.9042 |
| Gemma-4-12B-it | Author abstract | 189 | 0.5505 | 0.2705 | 0.3392 | 0.8888 |
| Qwen3-8B | GPT reference snapshot | 189 | 0.4693 | 0.1376 | 0.2536 | 0.8712 |
| Gemma-4-12B-it | GPT reference snapshot | 189 | 0.4764 | 0.1490 | 0.2733 | 0.8741 |

## GPT scores against complete papers

GPT-6.1 Sol (`gpt-6.1-sol`), medium reasoning, judged each saved Gemma summary against the complete extracted original PDF text, with page markers, in an independent ephemeral session. Tools and browsing were disabled. The judge received neither GPT reference summaries nor prior Qwen scores. All 200 source PDF hashes match the historical Qwen GPT evaluation. Extracted text includes tables where extractable; image-only content is not a substitute for visual inspection.

The historical Qwen rubric was reused with only the candidate name changed to Gemma. Scores range from 1 to 10. Accuracy receives 50% weight, coverage 25%, clarity 15%, and conciseness 10%. A `major_factual_error` flag requires accuracy at most 4 and caps the weighted total at 5; overall scores are then rounded to one decimal. Table means are independently recalculated from the saved per-paper values, rather than averages of rounded batch means.

| Dimension | Qwen mean (200) | Gemma mean (200) | Gemma median | Gemma minimum | Gemma maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 8.0815 | 8.5655 | 9.00 | 5.0 | 9.6 |
| Accuracy | 7.9885 | 8.5150 | 9.10 | 3.8 | 9.8 |
| Coverage | 8.0335 | 8.3250 | 8.40 | 6.3 | 9.2 |
| Clarity | 9.0670 | 9.2890 | 9.30 | 8.0 | 9.7 |
| Conciseness | 9.0165 | 9.5225 | 9.50 | 9.0 | 9.8 |

The Gemma judge returned **20 major-error flags**, compared with 37 in the historical Qwen ledger. These are automated scores-only judgments, not confirmed error counts or factual-error rates. The protocol intentionally saves no explanations or evidence quotations. Accuracy is not a percentage of correct claims, and a high overall score does not certify factual reliability. Gemma flagged paper IDs: paper019, paper030, paper037, paper047, paper048, paper068, paper081, paper082, paper083, paper089, paper095, paper124, paper129, paper136, paper138, paper142, paper157, paper186, paper191, paper197.

## Input provenance and comparison limits

The saved Gemma collection contains 200 nonempty summaries, each 158–203 whitespace-delimited English words. The teammate's generation status records `google/gemma-4-12B-it`, bitsandbytes NF4 4-bit double quantization, bfloat16 computation, SDPA, thinking disabled, seed 42, deterministic sampling, a 32,768-token context and a 27,000-token chunk setting. That status records 199 generated files and one skipped existing file; the precise generation provenance of the preserved file was not independently re-established. This evaluation covers all 200 saved files.

The GPT reference snapshot retains its mixed provenance: 175 GPT-6.1 Sol summaries and 25 preserved teammate summaries with unverified original model/prompt. It is a frozen reference collection, not a uniformly generated gold standard. Author-abstract section headings and trial-registration information were retained; abstracts were not shortened for scoring.

Qwen's historical outputs used Ollama Q4_K_M, whereas Gemma used a different runtime and quantization scheme. Generation prompts, effective input handling and dates were not controlled in a new paired experiment. The numeric judge knew the candidate name in both runs. Qwen judging occurred October 13 and Gemma judging October 23; the same judge model identifier does not pin an immutable backend version. Each paper was judged once, so repeated-judgment variability was not estimated. These factors limit causal comparisons and claims of model superiority.

The earlier [evidence review](independent_study_followup_2026-10-20.md) used a separate quote-backed protocol and an error-enriched subset for Qwen/GPT. Its counts must not be combined with Gemma's current numeric flags. Gemma has not yet received that equivalent evidence-backed error adjudication. No inference-throughput comparison was performed in this scoring run.

## Reproducibility and checks

ROUGE-1/2/L use stemming. BERTScore uses `roberta-large`, layer 17, encoder revision `722cf37b1afa9454edce342e7895e588b6ff1d59`, English, no IDF weighting, no baseline rescaling, slow tokenizer, CPU, batch size 1 and four threads. Both sides are normalized by joining whitespace-separated tokens with single spaces. Package versions match the Qwen run: torch 2.14.0, transformers 5.17.0, bert-score 0.3.13, rouge-score 0.1.2 and huggingface-hub 1.33.0. The recorded BERTScore descriptor is `roberta-large_L17_no-idf_version=0.3.12(hug_trans=5.17.0)`.

Validation checks 400 unique metric pairs, 200 unique GPT paper IDs, finite scores, candidate and reference hashes, unchanged original metric inputs, matching PDF hashes, the major-error cap, CSV/JSON agreement and independently recalculated aggregate means. Four independent tool-free GPT requests could run concurrently; result writes and exports were serialized. An initial workspace spend-cap interruption preserved completed rows; the run resumed without replacing them.

Metric input snapshot SHA-256: `583eeba3a2cc4b5b8bb89597d616a98a70b0756c32ca16ad9bd8aeef936d2953`.

Metric scorer SHA-256: `111669f05e5da101a9835a2e0f17923ba5ee33b657aba75b60131e6749f5192e`.

GPT rubric SHA-256: `ba27950117a37ab2ec007ba0b5ea8a28804b20e60c0b0d1a72d54680e0f8bb42`.

Final Gemma GPT scores CSV SHA-256: `6f9db3d7aac88565130e65650cab12ed5d0c99cb59afa9cc6e5c6e45c0e7ab65`.

Detailed outputs remain on gpu24 in `/data/SFT_demo/Oct/results/gemma_dual_reference_metrics_20261023/` and `/data/SFT_demo/Oct/results/gemma_gpt_scores_20261023/`. The latter includes the rubric, per-paper ledger, scores CSV, input hashes and completion status. Original summaries and prior Qwen results were preserved. This repository update publishes the English report only.
