# Factuality Calibration Execution

Current stage: the 10-paper / 20-candidate GPT evidence pilot is complete; independent human calibration is pending. This is not a completed 200-paper new factuality review.

Read `human_review/packet_en.md` and its 10 original PDFs first. Each reviewer should fill their own `reviewer_1.csv` or `reviewer_2.csv` before opening GPT findings. See `human_review/README_en.md`. Keep disagreements and independent originals; after discussion, record reconciled decisions in `independent_pilot.csv` and finding-level adjudication in `queue.csv`. Do not copy model verdicts into human fields.

`report_en.md` summarizes current automated findings. `optimization_notes_en.md` records the PDF reading-order diagnosis and preserved v1/v2 attempts. Only `gpt_evidence/calibration_v3/` supplies active pilot results. `verification.json` checks input hashes, quotations, pages, raw output identity, tool absence and completion. `inputs/selection.json` contains the frozen calibration and 20 additional unflagged-control IDs; it reveals selection labels, so keep it outside human-first reading.

The judge runs on the local Mac through the existing logged-in CLI, not a GPU24 model server. Requested model is gpt-6.1-sol/medium; the resolved backend snapshot identity is not independently exposed. One full-PDF candidate per tool-disabled session, at most two mechanical-validation retries, no hidden source truncation. A new judge/protocol/extraction creates a new version; never overwrite saved valid rows.

Local commands, run from the repository root:

```bash
python3 tools/export_factuality_review.py --root docs/factuality_review_20261031
python3 tools/verify_factuality_review.py --root docs/factuality_review_20261031
```

These refresh artifacts and audits without model calls. The export preserves existing finding-level human fields. `review_summary_factuality.py --root docs/factuality_review_20261031` only resumes the frozen 20-candidate pilot; it does not expand to 200 papers. All 20 accepted outputs already exist, so an unchanged resume makes no judge calls.

Shared server root: `/data/SFT_demo/Oct/results/factuality_review_20261031/`. New result artifacts are group-shared with sft; original paper/summary directories are preserved. `server_final_checks.json` records the final 200 original PDF and 800 original text hashes plus shared-result permissions.

No original summary was rewritten. The prior 5,400-request abstract-relevance benchmark remains separate from this full-paper factuality review. Complete human calibration before full Gemma evidence screening or a new summary-generation experiment.
