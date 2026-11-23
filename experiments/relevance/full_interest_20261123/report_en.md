# Full catalogue retrieval and Qwen reranking on GPU24

Run date: November 23, 2026. Hardware: NVIDIA H100L with a 24 GiB MIG allocation.

Both stages completed on GPU24. The job produced 400,000 cosine scores and 2,400 Qwen scores. The top-12 spot check found four clearly relevant MeSH headings outside the candidate pool, including one whose narrower equivalent was retrieved.

## Research question and unit of analysis

Can a full semantic pass produce a practical candidate pool for joint Qwen scoring, and what relevant concepts fall outside that pool? Each query in this study is one paper abstract, and each ranked item is a MeSH interest identified by its descriptor ID. Qwen reorders the 12 interests retrieved for that same paper. The teammate's study ranks papers for a fixed interest and compares its output to a Codex reference ordering. This report follows its approach to metric definitions, tie handling and item-level evidence. The two studies have different ranking directions, corpora and references, so their measurements answer different questions. [Teammate's ranking report](https://github.com/m2b3/Summarize_LLM_SFT/blob/0a69cacbf5dedd838cf2bff857c5a626213a631d/docs/reports/2026-11-13_nine_interest_ranking.md)

## Semantic retrieval

The run scored all 400,000 combinations of 200 frozen abstracts and 2,000 previously generated MeSH interests. The saved matrix contains 2,000 unique interest IDs and ranks per paper. Each paper contributed exactly 12 candidates for the reranker.

The CUDA embedding and cosine stage took 27.62 seconds, and the measured Python stage took 37.71 seconds including model initialization and result writing. The stage markers on the original launcher were 187 seconds apart, including Python startup, imports and the transition to Qwen. The initialization and startup costs should therefore be kept separate when comparing request throughput. The embedding baseline is all-MiniLM-L6-v2 at the revision in [the run record](run01/semantic_run.json). Abstracts used overlapping 256-token windows, and interest inputs combined the MeSH heading and definition. The catalogue was prepared using the same abstract collection.

## Qwen reranking

Qwen3.5-9B Q4_K_M scored the 12 candidates for each paper together on the frozen 0–100 rubric. The server ran four slots with 4,096 context tokens each and offloaded all 33 layers to the GPU. Each prompt fit the budget, with a maximum of 2,039 input tokens. The successful server startup took about 4 minutes 41 seconds. The first attempt exceeded the readiness timeout while reading the model, and the retry reused the existing semantic results. The measured reranking took **514.71 seconds** (8 minutes 35 seconds), excluding server startup and the final CSV export. Median and p95 per-request times were 10.19 and 11.55 seconds. Total elapsed time from the original semantic stage marker to job exit was **19 minutes 47 seconds**, including the initial timeout and restart.

All 200 responses contained the 12 expected IDs and integer scores in range. The model used 38 distinct score values across the run. Ties remained in 197 papers, and 62 had a tie at the highest Qwen score. Those ties use the original semantic rank. The run measured the behavior of the 100-point rubric without a matched comparison against the previous 0–3 rubric.

The private server shut down after the run, and reported GPU memory use returned to 1 MiB. See [the reranked scores](run01/qwen_scores.csv), [timing](run01/qwen_run.json), and [verification](verification.json).

## Ranking agreement within the candidate pool

For each paper, Top-*k* overlap counts descriptor IDs that appear in both the semantic and reranked Top-*k* lists. Overall overlap is the sum of intersections divided by 200 × *k*. Equal Qwen scores use semantic rank as the production tie-break. Both methods share the candidate set, so Top-12 overlap is 100% by construction.

| Cutoff | Shared placements | Overlap | Papers with identical Top-*k* sets |
| ---: | ---: | ---: | ---: |
| 1 | 83/200 | 41.5% | 83/200 |
| 3 | 292/600 | 48.7% | 20/200 |
| 5 | 586/1,000 | 58.6% | 11/200 |
| 10 | 1,825/2,000 | 91.3% | 70/200 |
| 12 | 2,400/2,400 | 100.0% | 200/200 |

Qwen changed the first-ranked interest for 117/200 papers under the production tie-break. If each highest-scoring interest were equally likely to be chosen, expected Top-1 agreement would be 28.8%. This sensitivity check gives a paper a contribution of 1 divided by the size of its highest-scoring group if that group contains the semantic winner, and zero otherwise. Both figures measure how much the rankings agree. Evaluating which ranking is more relevant requires separately judged interests for each paper. [Per-paper overlaps and tie groups](ranking_diagnostics.csv)

## Top-12 omission audit

The spot check used seed 20261123 to select six omitted literal heading hits from each of ranks 13–30, 31–100 and 101–2,000, with one pair per paper. For each pair, the assistant compared the heading definition against the full frozen abstract. The audit classifies a heading as clear when it describes the study question, the defining population or intervention, or a principal finding. The 18 sampled pairs yielded four clear, six secondary and eight incidental matches. The selection enriches for literal matches and likely misses synonyms and implicit concepts. These counts show that relevant omissions occur and do not estimate collection-wide recall or constitute independent human review.

| Paper | Omitted heading | Semantic rank | Why it matters |
| --- | --- | ---: | --- |
| paper193 | Inuit | 19 | The study focuses on Kalaallit Inuit birth culture and the impact of centralizing maternity services. |
| paper057 | Esophagectomy | 20 | The procedure defines the population in the discharge-readiness study. |
| paper037 | Digital Health | 30 | The trial evaluates fully online mental health interventions delivered through WeChat. |
| paper200 | Back Pain | 55 | Chronic low back pain defines the question and population. The narrower heading Low Back Pain was already retrieved at rank 12. |

For these four audited exact headings, widening the semantic pool would include 0/4 at *k*=12, 2/4 at *k*=20, 3/4 at *k*=30 and 4/4 at *k*=60. This is a retrospective check on omissions selected from beyond rank 12. [Audit ledger with all 18 pairs and exact abstract excerpts](top12_audit.csv)

## Next experiment

Freeze a shared set of paper–interest judgments, including candidates and interests outside the current cutoff. Compare Top-12 and Top-30 semantic retrieval with a semantic and lexical union under a stated candidate budget. Report candidate Recall@K against judged relevant IDs, final nDCG@K against graded judgments, the tie policy, and latency for each stage. With the current evidence, report overlap and the omission audit as separate results.
