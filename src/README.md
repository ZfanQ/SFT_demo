# Experiment Code Guide

[Repository home](../README.md) · [Reports](../docs/README.md)

## Current relevance review

| Script | Purpose |
| --- | --- |
| [review_relevance_population.py](review_relevance_population.py) | Resume the 600-pair review, reusing accepted judgments |
| [compare_relevance_population.py](compare_relevance_population.py) | Audit full-collection results and export reports and human forms |
| [review_relevance_scores.py](review_relevance_scores.py) | Original 60-pair pilot and shared review protocol |
| [compare_relevance_reviews.py](compare_relevance_reviews.py) | Pilot comparison and shared statistics |

See the [execution instructions](../experiments/relevance/relevance_review_full_20261106/README_execution.md) for commands and the teammate workflow. Judge drivers are fingerprinted in recorded protocols; changes require a new version.

## Other workflows

| Area | Starting points |
| --- | --- |
| Dataset preparation | [build_medical_paper_set.py](build_medical_paper_set.py) |
| Saved-summary metrics | [score_saved_summaries.py](score_saved_summaries.py), [score_abstract_gpt_baseline.py](score_abstract_gpt_baseline.py), [score_gemma_gpt.py](score_gemma_gpt.py) |
| Summary factuality | [prepare_factuality_triage.py](prepare_factuality_triage.py), [review_summary_evidence.py](review_summary_evidence.py), [verify_factuality_review.py](verify_factuality_review.py) |
| Concurrency benchmarks | [benchmark_feed_matrix.py](benchmark_feed_matrix.py), [benchmark_feed_matrix_llamacpp.py](benchmark_feed_matrix_llamacpp.py), [benchmark_feed_matrix_gemma.py](benchmark_feed_matrix_gemma.py) |
| Performance analysis | [analyze_feed_matrix.py](analyze_feed_matrix.py), [plot_feed_matrix.py](plot_feed_matrix.py) |

Read the corresponding dated report and script arguments before running an experiment. Resume and repair helpers retain their original names and paths. Automated checks live in [tests](../tests).
