# Full-Cohort Independent Relevance Review

Run started: November 6, 2026 (Asia/Shanghai).

The review covers **600/600 paper/profile pairs** from all 200 papers and three original interest profiles. It reuses **60 unchanged pilot judgments** and adds **540 new judgments**, producing **5400 comparisons** with the nine saved model/concurrency configurations.

## Method

The original 0–3 scale, interest profiles, abstracts, model identifier and reviewer instructions are retained. Each pair receives an isolated GPT session with prior model scores, model identities and concurrency hidden. Four independent sessions run concurrently; schema, quotation and input hashes are checked before acceptance. The imported pilot judgments keep their original bytes and provenance. Original model scores remain fixed.

## Agreement with the GPT reference

| Configuration | Concurrency | Reviewed pairs | Exact agreement | Within one point | Mean absolute difference | Difference ≥2 | Score-2 boundary disagreements |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3_8b | 2 | 600 | 75.5% | 99.0% | 0.255 | 6 | 19 |
| qwen3_8b | 4 | 600 | 75.8% | 99.2% | 0.250 | 5 | 18 |
| qwen3_8b | 8 | 600 | 75.8% | 99.2% | 0.250 | 5 | 18 |
| qwen35_9b_llamacpp | 2 | 600 | 86.0% | 99.5% | 0.145 | 3 | 16 |
| qwen35_9b_llamacpp | 4 | 600 | 86.5% | 99.3% | 0.142 | 4 | 16 |
| qwen35_9b_llamacpp | 8 | 600 | 86.7% | 99.2% | 0.142 | 5 | 16 |
| gemma4_12b_llamacpp | 2 | 600 | 84.3% | 99.8% | 0.158 | 1 | 11 |
| gemma4_12b_llamacpp | 4 | 600 | 84.8% | 99.8% | 0.153 | 1 | 11 |
| gemma4_12b_llamacpp | 8 | 600 | 85.2% | 99.8% | 0.150 | 1 | 9 |

## Teammate review files

- [All 200 papers](paper_overview.csv): one row per paper, with the three GPT scores and priority flags.
- [Independent human scoring form](human_review/independent_scores.csv): all 600 original tasks, with blank human-score fields.
- [Prioritized comparison queue](human_review/priority_queue.csv): GPT evidence, all saved model scores and editable human decisions.
- [Detailed paired comparisons](comparisons.csv) and [per-profile metrics](per_profile_summary.csv).

The current queue has **28 high-priority pairs**, **24 scope-ambiguous pairs**, and **20 agreement controls**. High priority marks a score difference of at least two points or a disagreement across the score-2 relevance boundary. Human reviewers can begin with the independent form, then reconcile priority cases and controls against GPT evidence.

## Interpretation and continuation

These tables measure agreement with the independent GPT reference across the full frozen collection. The collection has its original profile/topic distribution; compare per-profile results when interpreting changes from the score-balanced pilot. The teammate supplies human calibration and resolves scope boundaries. Any refined scale or profile starts a new version.

Partial runs identify pending GPT pairs in the overview and queue. Accepted judgments resume without regeneration. Service or quota failures stop new submissions while preserving completed and in-flight results. Publication remains in the experimental repository until credibility review and user confirmation.
