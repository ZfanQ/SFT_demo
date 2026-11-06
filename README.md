# SciCommons: Summarization and Relevance Experiments

Experimental workspace for evaluating scientific-paper summaries, relevance scoring and local-model performance.

## Start here

| Task | Entry point |
| --- | --- |
| Read the latest results | [Full-collection relevance report](docs/relevance_review_full_20261106/report_en.md) |
| Perform human calibration | [Reviewer instructions](docs/relevance_review_full_20261106/README_execution.md#teammate-handoff) |
| Find earlier reports and meeting records | [Report directory](docs/README.md) |
| Find experiment scripts | [Code guide](tools/README.md) |
| Understand the project background | [Archived project overview](docs/project_background.md) |
| Check publication rules | [Publication policy](docs/PUBLISHING.md) |

## Current work

The independent GPT relevance review covers **200 papers × three interest profiles = 600 judgments**, compared with **5,400 saved model scores**. Automated checks are complete; the teammate handles human calibration.

1. Use the [independent scoring form](docs/relevance_review_full_20261106/human_review/independent_scores.csv) to record human scores before viewing GPT scores.
2. Reconcile decisions using the [comparison queue](docs/relevance_review_full_20261106/human_review/priority_queue.csv): 28 high-priority pairs, 24 scope ambiguities and 20 agreement controls, with possible overlap.
3. Use the [200-paper overview](docs/relevance_review_full_20261106/paper_overview.csv) to locate each paper across profiles.

GPT agreement is an automated reference pending human calibration. Summary factuality is tracked separately in the [factuality pilot](docs/factuality_review_20261031/report_en.md).

## Repository map

| Directory | Contents |
| --- | --- |
| `docs/` | Reports, review forms, frozen experiment inputs and raw evidence |
| `tools/` | Data preparation, evaluation, benchmarking and audit scripts |
| `tests/` | Automated checks for evaluation and experiment tooling |
| `local_test/` | Original local summarization workflow and baseline materials |
| `Meetings/` | Meeting materials |

Dated experiment folders preserve reproducible snapshots. Their paths remain stable; use the report directory to navigate them.

Testing work is published here in **ZfanQ/SFT_demo**. Supervisor-facing publication to **m2b3/Summarize_LLM_SFT** follows credibility review and user confirmation.
