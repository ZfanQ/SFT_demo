# Factuality Review: Source-Linked GPT Calibration

Source-blinded GPT review of 20 saved summaries across 10 papers produced **13 concerns**, including **12 source-contradiction labels**. Source quotations and PDF-page checks support a review queue ready for independent human calibration.

## Coverage

- Frozen papers: 200. Historical Qwen/GPT full-text review: 83 selected papers.
- Historical Gemma scores-only flags: 20, used to guide sample selection.
- Source-blinded calibration: 20/20 candidate reviews across 10 papers.
- Human-reviewed finding rows: 0; recorded human-confirmed errors: 0.
- Twenty additional historically unflagged control papers were selected before review and reserved for independent human reading.
- Review queue: 100 records spanning historical findings, numeric flags and new concerns. Article-level counts require deduplication of overlapping records.

## Method

Five previously Gemma-flagged and five unflagged papers each contribute saved Qwen and Gemma summaries. Each GPT session receives one anonymous candidate and its full article. Candidate labels vary by paper; model identities and prior scores are hidden.

Automated validation checks the candidate quotation and the cited source text on the specified PDF page. The review distinguishes contradictions from unsupported or uncertain claims. Original PDFs and summaries remain unchanged.

## Automated concerns

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

## Extraction improvement and verification

Reading-order re-extraction corrected interleaved PDF columns for the ten papers while preserving PDF hashes and page counts. Results use the revised text; earlier diagnostics remain archived. See [optimization notes](optimization_notes_en.md), `inputs/reading_order_checks.json`, and `verification.json`.

## Interpretation and human calibration

Independent readers assess whether the source context supports each GPT concern and whether it materially changes the summary. Human calibration is pending; recorded confirmations remain zero.

The enriched sample supports workflow calibration and case analysis. Population error rates and model rankings require appropriately sampled evaluation. GPT-family reviewer preferences are a potential bias, including for GPT-written references.

## Human review procedure

1. Read [the blinded packet](human_review/packet_en.md) and PDFs before consulting GPT findings or source mappings. Each reviewer records judgments in a separate copy of `human_review/independent_pilot.csv`.
2. Reconcile judgments with `human_review/queue.csv`; record confirmed, rejected or unresolved concerns and supporting context.
3. Locate unindexed historical quotations in the PDFs and verify source hashes before reusing judgments. Blank human-verdict fields remain unreviewed.

## Next steps

Resolve reviewer false alarms, misses and systematic interpretation problems through independent calibration. Then audit corrected extraction across the 200 Gemma papers and extend the evidence review. Preserve protocol versions and save any edited summaries as separate outputs.
