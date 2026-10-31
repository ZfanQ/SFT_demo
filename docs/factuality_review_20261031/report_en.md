# Factuality Review: Evidence Pilot and Human Calibration

This report separates automated suspicions from human decisions. Original PDFs and summaries remain unchanged.

## Coverage

- Frozen papers: 200. Historical Qwen/GPT full-text review: 83 selected papers.
- Historical Gemma scores-only flags: 20. These flags are not confirmed errors.
- New blinded calibration: 20/20 candidate reviews, across 10 selected papers.
- New automated findings: 13; source-contradiction labels: 12.
- Human-reviewed findings: 0; human-confirmed errors: 0. Zero confirmations before human review is not evidence of zero errors.
- Twenty separate historically unflagged control papers were selected before new reviews. They remain reserved for independent human reading.
- Review queue: 100 rows, including historical findings, numeric flags and new findings. These overlap and are not a count of unique errors or affected summaries.

## Human review workflow

Start with [the blinded packet](human_review/packet_en.md) and record independent decisions in `human_review/independent_pilot.csv`, saving a separate copy per reviewer. Do not open GPT findings or the private mapping first. Then reconcile source evidence using `human_review/queue.csv`. Candidate labels differ by paper.

The queue contains older source-quoted findings, historical numeric flags without evidence, and any new page-linked findings. A blank human verdict means unreviewed. A source hash mismatch invalidates direct reuse. Historical exact quotations were not independently page-indexed by the old protocol and require PDF location checking.

## New automated findings

| Paper | Blinded candidate | Status | Priority | PDF page | Candidate claim |
| --- | --- | --- | --- | ---: | --- |
| paper019 | B | contradicted | high | 5 | the pipeline correctly identified expansions in 82% of DM1 subjects |
| paper024 | A | contradicted | high | 9 | These effects remained significant after controlling for autoregressive pathways, worry, rumination, avoidance, and childhood adversity. |
| paper024 | B | contradicted | high | 12 | Specifically, the indirect effects for depression (0.13, $p = .036$), anxiety (0.16, $p = .030$), and somatic symptoms (0.54, $p = .036$) were significant. |
| paper039 | A | contradicted | high | 6 | a truncated CPT training for 98 clinicians across 34 organizations |
| paper047 | B | contradicted | high | 6 | 46% were asymptomatic or in remission by 2003 |
| paper082 | A | contradicted | high | 8 | Furthermore, fiber supplementation significantly reduced insulin-mediated carbohydrate oxidation (p=0.027) and fat oxidation (p=0.006) compared to the placebo. |
| paper082 | B | contradicted | high | 5 | The 12-week randomized, placebo-controlled trial involved 44 participants, with 19 receiving the fiber mixture and 23 receiving maltodextrin as a placebo. |
| paper083 | B | contradicted | high | 6 | showing lower rates of microscopic hematuria than both other groups |
| paper156 | B | contradicted | medium | 4 | Limitations include the use of a single cell line |
| paper157 | A | contradicted | high | 17 | an effect mitigated by the LXRα antagonist SR9243 |
| paper157 | A | unsupported_in_reviewed_material | medium | 17 | Human data corroborated these findings, showing that elevated ratios of specific lysophospholipids and ceramides correlated with higher clinical activity scores. |
| paper157 | B | contradicted | high | 15 | However, the study did not establish causality |
| paper193 | B | contradicted | high | 4 | 20 pregnant women and their families |

Exact quotations and page provenance are automatically checked against supplied text. That does not validate the model's interpretation; humans must check context, numbers, tables, figures and uncertainty.

This pilot is deliberately enriched with five previously flagged and five unflagged Gemma papers. It cannot estimate overall error rates or establish a model ranking. GPT-family judgments may favor related models; reference summaries are not factual gold labels.

## Extraction correction and execution audit

A bounded initial trial exposed interleaved columns in the historical PDF extraction. The ten calibration PDFs were re-extracted in reading order, with original file hashes and PDF page counts preserved. The old text and trial outputs remain archived; only the separately versioned active protocol contributes to this report. See [optimization notes](optimization_notes_en.md), `inputs/reading_order_checks.json`, and `verification.json`.

## Next gate

Obtain independent human calibration and resolve systematic reviewer failures before extending the new evidence protocol to all 200 Gemma summaries. Apply and audit the corrected extraction method before that expansion. Do not auto-correct source summaries. Preserve older and new protocols separately. This run does not change or validate the separate relevance-throughput experiment.
