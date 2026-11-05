# Independent Relevance-Score Review

This experiment checks the existing 0–3 abstract-relevance scores using an independent GPT reference. It uses the original scale, profiles and abstract inputs from the October 31 concurrency matrix.

## Workflow

1. Freeze the source dataset and score ledgers. Sample 20 paper/profile pairs per profile: five from each Qwen3-8B/p2 score stratum, seed 42. There are 60 unique pairs.
2. Provide one original task/abstract per fresh GPT session, withholding all saved model scores, model identities, concurrency settings and sampling labels. Reviewer sessions run in isolated temporary directories with model tools and browsing disabled.
3. Collect an independent 0–3 score, exact abstract evidence, rationale and scope-ambiguity flag. Validate each response and preserve raw attempts before accepting it.
4. Compare the independent judgments with all nine saved model/concurrency configurations on the same pairs: 540 comparisons when complete.
5. Export an independent human scoring form, a priority queue, exact agreement, within-one agreement, mean absolute difference, large differences and score-2 boundary disagreements.

The original 5,400 scores stay fixed. The balanced sample is a diagnostic cohort; its agreement percentages describe the selected pairs. Independent human labels calibrate how well the GPT reference tracks the intended relevance criteria.

## Files

- `inputs/requests.json`: exact independent-review inputs and input hashes.
- `inputs/selection.json`: selection IDs and baseline strata; keep this outside blind review.
- `inputs/source_scores.json`: saved scores, withheld from GPT.
- `inputs/manifest.json`: original dataset and ledger hashes.
- `gpt_reviews/`: frozen protocol, accepted judgments, raw responses/events and request text.
- `status.json`: running, partial, complete or needs-attention state.
- `summary.json`, `configuration_summary.csv`, `per_profile_summary.csv`, `comparisons.csv`: audited comparison results.
- `human_review/independent_scores.csv`: abstract/profile inputs with blank human-score fields.
- `human_review/priority_queue.csv`: GPT reference, all saved scores, differences and preserved human fields.
- `report_en.md`: English report generated from accepted results.

Read the independent form before the GPT reference or priority queue when providing human labels. If you have already seen model scores, record that exposure in your review reason. Scope ambiguity should lead to an explicit later rubric/profile revision; the current original-score version remains intact.

## Commands

From the repository root:

```bash
python3 -B tools/review_relevance_scores.py --root docs/relevance_review_20261105 --prepare-only
python3 -B tools/review_relevance_scores.py --root docs/relevance_review_20261105 --limit 3
python3 -B tools/review_relevance_scores.py --root docs/relevance_review_20261105
python3 -B tools/compare_relevance_reviews.py --root docs/relevance_review_20261105
python3 -B -m unittest discover -s tests -p test_relevance_review.py
```

Preparation and comparison are local standard-library operations. Judging uses the existing local logged-in Codex CLI with requested model `gpt-6.1-sol` and medium reasoning. The immutable provider-side model snapshot is not exposed. Mechanical validation allows two retries in fresh sessions; failed attempts remain saved. The source/protocol fingerprint guards resumed runs, and accepted judgments are reused without new requests.

The judge executable path is Mac-specific. On GPU24, the copied comparison script can audit saved results with `--source /data/SFT_demo/Oct/results/feed_matrix_20261031`; model calls continue to use the local login. Experimental publication goes to ZfanQ/SFT_demo. Supervisor-facing publication follows the credibility-review process in `docs/PUBLISHING.md`.
