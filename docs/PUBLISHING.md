# Experimental and Supervisor-Facing Publication

User instruction recorded November 5, 2026: publish the testing work in `ZfanQ/SFT_demo` first, and share curated results with the supervisor only after their credibility has been reviewed and confirmed.

## Destinations

| Repository | Purpose | Next publication behavior |
| --- | --- | --- |
| [ZfanQ/SFT_demo](https://github.com/ZfanQ/SFT_demo) | Experimental code, prompts, preliminary reports, diagnostics and validation work | Default destination for test-stage commits and pushes |
| [m2b3/Summarize_LLM_SFT](https://github.com/m2b3/Summarize_LLM_SFT/tree/main) | Supervisor-facing English reports and selected supporting figures/tables | Further publication waits for credibility review and user confirmation; no automatic mirroring |

This changes the destination of subsequent work. Earlier supervisor-facing reports retain their historical scope and pending-validation labels; this instruction does not request their deletion or a history rewrite.

## Current status

- The 200-abstract concurrency matrix has 5,400 technically validated scoring responses. The tests establish recorded throughput, latency and score stability, with documented backend differences. They do not establish relevance accuracy.
- The factuality pilot has twenty source-blinded summary reviews and thirteen automated concerns. Exact source quotations and PDF pages were checked after correcting a two-column extraction issue. The archived snapshot has no recorded independent human calibration.
- [Independent GPT relevance review](../experiments/relevance/relevance_review_20261105/report_en.md) is complete for 60 stratified paper/profile pairs and 540 comparisons with saved scores. It retains the original 0–3 scale and records abstract evidence, rationale and scope ambiguity. Independent human relevance calibration is the next step.
- [Full-collection relevance review](../experiments/relevance/relevance_review_full_20261106/report_en.md) extends the same protocol to all 200 papers and three profiles: 600 GPT judgments and 5,400 comparisons. Sixty pilot judgments are preserved byte for byte, with 540 new judgments. The teammate's packet includes all 600 tasks, 28 high-priority pairs, 24 scope ambiguities and 20 agreement controls; human calibration is pending.

## Evidence required before promotion

1. **State the claim and cohort.** Identify whether the result concerns summary factuality, relevance accuracy, ranking agreement or inference performance. Record source versions, model/backend, rubric and sample selection.
2. **Finish the relevant checks.** Validate input identity, complete outputs, source-linked evidence and recalculated statistics. For performance, preserve actual engine concurrency and timing boundaries. For content-quality claims, complete the planned independent human calibration and record disagreements, false alarms, misses and review denominators.
3. **Respect the experiment's limits.** An enriched sample is not a population error-rate estimate. GPT agreement or self-reported confidence is not calibrated correctness. Throughput alone does not select the best model for quality. A limited but well-supported finding may be reported with its exact scope.
4. **Prepare an English report for review.** Include the question, method, results, uncertainty, completed/pending validation and the experimental source commit. Select figures/tables that support the stated claim; keep full diagnostics and raw experiment materials in their experimental store.
5. **Obtain the user's confirmation before sharing with the supervisor.** Technical checks passing alone do not trigger that publication. Once confirmed, use a normal reviewed commit and verify the destination and published state.

If inputs, extraction, scoring rules or reviewer configuration change, preserve earlier results and create a new version. Do not silently rewrite historical scores, source summaries or verdicts to make the comparison appear consistent.

## Follow-up work

The teammate handles independent human calibration. Use the full-collection relevance forms for the 600 tasks, prioritizing score-2 boundary disagreements and differences of at least two points, alongside scope ambiguities and twenty agreement controls. The earlier 60-pair snapshot retains its six controls. Continue the separate factuality calibration with its existing packet. Freeze a new rubric version if the original coarse 0–3 definitions are refined.

The follow-up remains experimental until the above evidence has been reviewed. The complete 200-paper factuality extension remains pending.

## November 6 combined progress publication

The user explicitly authorized combining the performance benchmark and full GPT relevance review for the supervisor repository. The curated English report and aggregate tables are retained in `publications/2026-11-06_relevance_speed_quality/`. This publication reports measured performance and automated GPT agreement, with teammate human calibration pending. It does not promote GPT scores to human-validated accuracy. Earlier reports retain their original snapshots.
