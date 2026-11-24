# Candidate budget and tie comparisons for paper-to-interest ranking

## Progress summary for November 23–24

We ran semantic matching on all **200 abstracts × 2,000 MeSH interests** and used Qwen to score and rerank the top 12, 30, or 50 candidates for each paper. A larger pool recovered more relevant labels in the audit, but the 50-interest scoring run was sensitive to input order. Top-30 remains the provisional baseline for displaying five interests.

- **Candidate coverage.** Of 12 clearly relevant labels identified in a targeted audit of Top-12 omissions, Top-30 recovered 5 and Top-50 recovered 9. After Qwen scoring and the standard semantic tie-break, 2 of those labels appeared in the Top-30 lists' first five positions and 1 appeared in the Top-50 lists' first five. These counts describe the audited omissions. [Coverage and visibility details](#candidate-omissions)
- **Tie comparison.** A second Qwen pass reduced the number of papers tied for first from 136 to 63. In a blinded assistant review of 12 changed choices, 3 favored Qwen's adjustment, 7 favored the original semantic order, and 2 had no clear preference. [Blinded spot check](#blinded-spot-check-of-changed-choices)
- **Input order.** For 24 papers, we scored the same 50 interests in forward and reverse order. Across the 480 paired labels that moved between the first and last ten input positions, the zero-score rate rose from 72.7% early to 97.9% late. The two Top-5 lists shared 21 of 120 placements, fewer than one per paper on average. [Order control](#november-24-follow-up-on-score-stability)

**Next step.** Score the same candidates in smaller groups and repeat the order control to see whether the scores and the first five interests become more stable.

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

## November 24 follow-up on score stability

The saved Top-50 score vectors show a concentration of zero scores late in the prompt. The first 10 positions received 1,374 zeros out of 2,000 scores (68.7%). The last 10 received 1,881 out of 2,000 (94.1%). Across the entire arm, 8,432 of 10,000 scores were zero, and 22 papers received zero on all 50 interests. The inputs were ordered by descriptor ID, so the observed difference could reflect the descriptors that occupy those positions, where they appear, or both. [Per-position counts for all three arms](score_position_diagnostics.csv)

The GPU24 control scored the same 50 descriptors in forward and reverse order for 24 papers. It kept the Qwen3.5-9B checkpoint, rubric, response format, four request slots, and context and output budgets fixed. The frozen panel included the nine clear omissions that entered Top-50 and 15 papers drawn at random from the remaining papers. The assigned execution order started with forward for 12 papers and reverse for 12. All 48 requests completed in 168.69 seconds with zero retries. The server offloaded all 33 model layers. [Frozen sample](position_control_sample.json) · [Run configuration](position_control_20261124/run01/config.json) · [Timing](position_control_20261124/run01/timing.json)

| Paired outcome | Result |
| --- | ---: |
| Paper–interest scores changed after reversal | 288/1,200 (24.0%) |
| Mean absolute score change after reversal | 14.05/100 |
| Mean absolute change between the two forward runs | 1.63/100 |
| Zero scores overall, forward and reverse | 1,071/1,200 (89.3%) and 1,032/1,200 (86.0%) |
| Same interests scored zero when placed in the first 10 and last 10 | 349/480 (72.7%) and 470/480 (97.9%) |
| Shared Top-5 placements | 21/120 (17.5%) |
| Papers retaining the same complete Top-5 set | 0/24 |
| Papers retaining the same first interest | 3/24 |

The first-to-last calculation uses the same 20 descriptors per paper that cross between the first 10 and last 10 input positions. Of the 480 paired descriptors, 128 went from nonzero early to zero late, and seven changed in the opposite direction. All 24 papers had more zero scores among these descriptors when they appeared late. The 15 randomly drawn papers showed the same pattern, from 226/300 zeros early to 300/300 late. Top-5 overlap uses exact IDs and the same original semantic rank to break equal scores in both arms. Three papers received all zeros in forward order and two in reverse order, so their Top-5 lists consist entirely of the semantic ranking. [Paired scores](position_control_20261124/paired_scores.csv) · [Per-paper Top-5 sets](position_control_20261124/top5_comparison.csv) · [Verified summary](position_control_20261124/summary.json)

Position sensitivity also affected the earlier audited labels. Esophagectomy moved from position 36 to 15 and its score rose from 0 to 100, moving its rank from 21 to 1. Glomerular Filtration Rate moved from position 15 to 36 and fell from 60 to 0, moving its rank from 3 to 20. Overall, one of the nine audited labels appeared in the forward Top-5 and two appeared in the reverse Top-5. [Audited labels and both rankings](position_control_20261124/audited_labels.csv)

For this panel, the control shows that changing the descriptor order changes scores and display choices. It measures sensitivity to the order of the full list, which also changes the surrounding descriptors. It does not establish that reverse ordering is more accurate. The next diagnostic should score the same candidates in shorter groups and repeat the order check. Independent relevance judgments are needed to measure whether the resulting Top-5 rankings improve.
