# Candidate budget and tie comparisons for paper-to-interest ranking

The experiment compares three candidate budgets for assigning research interests to each of 200 frozen abstracts. It reuses the 400,000 cosine scores from the preceding all-MiniLM-L6-v2 run and the same 2,000 MeSH descriptor IDs. Each paper receives a ranking of interests. The earlier run and the Top-50 extension share a GPU24 model family and a 100-point rubric, with the protocol below defining a fresh matched comparison across all three budgets. [Frozen source run](../full_interest_20261123/report_en.md)

## Matched protocol

All three arms use Qwen3.5-9B Q4_K_M, temperature 0, seed 42, four request slots and an 8,192-token context per slot. Each paper is sent in a single request for each budget. Labels and definitions appear in stable descriptor-ID order, and the response returns one integer score in 0–100 per position. The server tokenizer is checked against the model tokenizer, and the driver verifies the context budget and the exact score count. Score-vector positions are mapped back to descriptor IDs for validation and reporting. The arms run sequentially in increasing candidate-budget order on one private inference service.

The control ranks items by descending Qwen score, then by their original semantic rank. In the Top-50 arm, a second Qwen call compares each equal-score group involving first place or spanning the rank-5 boundary. The model uses the abstract and descriptor definitions to return relevance tiers and an evidence quote. A tier can contain several interests. If the quote cannot be found in the abstract, the original tie remains intact. The display includes the entire tier at the fifth position, so displayed lists can exceed five items.

## Scoring time and score stability

| Semantic candidate budget | Completed scores | Reranking wall time | Maximum input tokens | Papers tied at the highest score |
| ---: | ---: | ---: | ---: | ---: |
| 12 | 2,400 | 258.02 s | 1,821 | 121/200 |
| 30 | 6,000 | 479.95 s | 3,066 | 145/200 |
| 50 | 10,000 | 710.57 s | 4,590 | 136/200 |

Each row uses 200 papers and four concurrent request slots. Wall time includes formatting, tokenization, scoring, output validation and per-request checkpoint writes. It excludes the shared server startup and final CSV export. All three arms completed without invalid scoring responses or retries. The Top-50 arm took 230.62 seconds longer than Top-30, an increase of 48.1%. [Top-12 timing](run01/k12/timing.json) · [Top-30 timing](run01/k30/timing.json) · [Top-50 timing](run01/k50/timing.json)

| Candidate budgets compared | Shared paper–interest pairs | Scores exactly equal | Mean absolute change out of 100 |
| --- | ---: | ---: | ---: |
| 12 and 30 | 2,400 | 1,281 | 18.35 |
| 12 and 50 | 2,400 | 1,236 | 23.65 |
| 30 and 50 | 6,000 | 4,173 | 14.21 |

Shared scores are matched by exact paper and descriptor IDs. The same paper–interest pair can receive different scores when the surrounding interest list changes. These comparisons measure score stability across candidate budgets. Positional validation checks the length and range of each vector, and it cannot independently certify the semantic assignment of every score.

## Candidate omissions

The earlier audit contributed 18 paper–interest pairs. A second audit sampled six literal heading hits in each of ranks 13–30, 31–50 and 51–100, using seed 501230. It used one pair per paper and excluded papers from the first audit. The assistant reviewed the full abstract and heading definition, classifying a match as clear if the heading described the main research question, the defining population or intervention, or a principal finding. Eight of the new cases were clear, eight secondary, and two incidental.

| Semantic candidate budget | Clear audited headings included | Clear audited headings still outside |
| ---: | ---: | ---: |
| 12 | 0/12 | 12/12 |
| 30 | 5/12 | 7/12 |
| 50 | 9/12 | 3/12 |

The increase from 30 to 50 includes four examples at ranks 36–43. The remaining three clear labels occur at ranks 55, 66 and 81. The rank-55 label has a narrower equivalent already at rank 12. These fractions describe 12 clearly relevant labels from a set of 36 targeted, literal-hit omissions. All were outside Top-12 by design, and the fractions do not estimate collection-wide recall. [New audit with evidence](candidate_omission_audit.csv) · [Earlier audit](../full_interest_20261123/top12_audit.csv)

## Visibility after scoring and tie comparison

| Output | Clearly relevant audited omissions in the candidate pool | Audited omissions displayed |
| --- | ---: | ---: |
| Top-12, first five by score and semantic tie-break | 0/12 | 0/12 |
| Top-30, first five by score and semantic tie-break | 5/12 | 2/12 |
| Top-50, first five by score and semantic tie-break | 9/12 | 1/12 |
| Top-50, with comparison tiers and full boundary ties | 9/12 | 3/12 |

The Top-50 final display includes three audited labels. Glomerular Filtration Rate was already third, Diabetes Mellitus entered after comparison, and Inflammation entered through inclusion of the whole boundary tie despite a Qwen score of 0. The additional displayed count therefore mixes a preference change and a wider display. For the same abstract, Inuit ranked first with 85 in Top-30 and 21st with 0 in Top-50. A larger pool retrieved more clearly relevant labels but did not consistently put them in the first five. [Per-label scores, ranks and visibility](clear_omission_outcomes.csv)

## Effect of additional comparison

The Top-50 arm generated 243 critical same-score groups across 183 papers. There were 136 first-place groups and 160 groups spanning the fifth position, with 53 groups meeting both criteria. The comparison returned an exact, checked abstract quote for 194 groups. It split 154 of those groups and left 40 intact. For the remaining 49 groups, the original tie was kept. Of those, 31 responses reached the output limit twice and 18 completed with quotes that did not match the abstract.

After comparison, 63/200 papers still had a tie in the highest tier, down from 136/200. The original semantic winner fell outside the highest tier for 48/200 papers. The final display had more than five items for 122/200 papers because boundary ties were included in full. The final display membership differed from the fixed five-item baseline for 158 papers, including changes due to list length.

The successful comparison pass took **1,054.85 seconds (17 min 35 s)** and reused 12 groups from the first pass. The first pass stopped when the model returned two equal tier labels numbered 2 rather than 1. The revised validator uses the relative order of labels in the original rubric and preserves the original tie after two invalid outputs. The initial and revised job records preserve this change. From the start of the first scoring arm to verified job exit, wall time was **43 min 46 s**, including restart and the early comparison pass. [Timing](run01/ties/timing.json) · [Comparison ledger](run01/ties/decisions.json) · [Final display](run01/ties/display.json) · [Validation revision](run01/tie_validation.json)

## Blinded spot check of changed choices

Six strict changes at first place and six strict preference changes across the fifth-place boundary were sampled with seed 501205, using distinct papers. Candidate labels were randomized to A and B. The assistant assessed only the abstract and definitions, then unblinded which item each method favored. Among these 12 changed cases, 3 favored Qwen's comparison, 7 favored the original semantic ordering, and 2 had no clear preference. The audit concerns selected reversals and is neither an independent human review nor an estimate of population ranking accuracy. For example, comparison correctly promoted Chronic Cough over Asthma for a chronic-cough cohort, but incorrectly favored a childhood fluency disorder over Myasthenia Gravis for a study explicitly about myasthenia gravis. [Blinded pair judgments and excerpts](tie_comparison_audit.csv)

Top-50 is useful for finding more candidate labels. Top-30 is the provisional baseline for a five-item display because it took less time and surfaced two of the audited labels before tie comparison. A larger labeled set is needed to select a production budget. The present second-pass prompt reduced ties but took more time than initial Top-50 scoring, and its changed choices did not improve the blinded sample overall. Keep explicit ties and use the semantic rank for stable ordering when a strict display limit requires one. Stronger relevance judgments and a shorter, evidence-constrained comparison prompt would make a useful next comparison.
