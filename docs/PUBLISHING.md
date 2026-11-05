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
- Independent GPT checking of the 0–3 relevance scores is proposed, not completed. It needs its own rubric, sample, evidence and human calibration; the summary-factuality pilot cannot stand in for it.

## Evidence required before promotion

1. **State the claim and cohort.** Identify whether the result concerns summary factuality, relevance accuracy, ranking agreement or inference performance. Record source versions, model/backend, rubric and sample selection.
2. **Finish the relevant checks.** Validate input identity, complete outputs, source-linked evidence and recalculated statistics. For performance, preserve actual engine concurrency and timing boundaries. For content-quality claims, complete the planned independent human calibration and record disagreements, false alarms, misses and review denominators.
3. **Respect the experiment's limits.** An enriched sample is not a population error-rate estimate. GPT agreement or self-reported confidence is not calibrated correctness. Throughput alone does not select the best model for quality. A limited but well-supported finding may be reported with its exact scope.
4. **Prepare an English report for review.** Include the question, method, results, uncertainty, completed/pending validation and the experimental source commit. Select figures/tables that support the stated claim; keep full diagnostics and raw experiment materials in their experimental store.
5. **Obtain the user's confirmation before sharing with the supervisor.** Technical checks passing alone do not trigger that publication. Once confirmed, use a normal reviewed commit and verify the destination and published state.

If inputs, extraction, scoring rules or reviewer configuration change, preserve earlier results and create a new version. Do not silently rewrite historical scores, source summaries or verdicts to make the comparison appear consistent.

## Follow-up work

Continue independent human calibration of the existing factuality packet. Develop and test relevance-score review in this experimental repository: hide the candidate model and score from the GPT reviewer, obtain an independent score and supporting abstract evidence, compare with the saved scores, and prioritize threshold crossings/large disagreements plus randomly sampled agreements for human checking. Freeze a new rubric version if the original coarse 0–3 definitions are refined.

The follow-up remains experimental until the above evidence has been reviewed. This document does not claim that a new GPT relevance experiment or a complete 200-paper factuality review has already run.
