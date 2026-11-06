# Full-collection relevance review

This run extends the independent GPT relevance review to all 200 original abstracts and three fixed interest profiles: 600 paper/profile pairs. The source matrix contains nine model/concurrency configurations and 5,400 saved scores.

The original task, 0–3 scale, reviewer model and response schema are retained. Sixty pilot judgments and their raw records are reused byte for byte; 540 additional judgments complete the collection. Each new judgment uses an isolated session with source model scores hidden and tools disabled. Four sessions run concurrently. Mechanical validation can request a corrected response; service or quota errors stop new submissions and preserve accepted results.

## Run and resume

From the repository root:

```sh
python3 -B -u tools/review_relevance_population.py --root docs/relevance_review_full_20261106
python3 -B tools/compare_relevance_population.py --root docs/relevance_review_full_20261106
```

An exclusive lock prevents concurrent controllers. A resumed run verifies source hashes, protocol identity and accepted judgments before submitting pending pairs. `status.json` records progress; `summary.json` and the English report describe the most recent audited export.

## Teammate handoff

- `paper_overview.csv`: 200 papers, with results and review priority for each profile.
- `human_review/independent_scores.csv`: 600 tasks with original inputs and blank human fields. Review this form first to keep the initial human scores independent of GPT.
- `human_review/priority_queue.csv`: the same tasks ordered by disagreements, scope ambiguity and agreement controls, with GPT evidence and all nine saved scores for reconciliation.
- `report_en.md`: audited counts, agreement statistics and interpretation.

Fill human fields in a working copy and retain the supplied snapshot. The exporter preserves populated human fields when updating its own forms. GPT agreement is an automated reference; the teammate's calibration supplies the human assessment. Refined profiles or scoring rules should start a new version.

Publication goes to `ZfanQ/SFT_demo`. Further sharing with the supervisor follows the review and confirmation process in `docs/PUBLISHING.md`.
