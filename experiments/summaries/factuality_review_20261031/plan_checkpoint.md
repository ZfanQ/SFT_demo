# Evidence-Based GPT Screening and Human Review Implementation Plan

**Goal:** Turn existing summary evaluations into a source-linked review queue, calibrate GPT factuality screening against independent human reading, and extend evidence review without changing saved summaries.

**Architecture:** Reuse the existing frozen source collections and quote-backed Qwen/GPT reviews. Add Gemma under a versioned, blinded full-text protocol; validate quotations and source identity automatically, then export an editable human review queue. Keep automated suspicions, human decisions and edited summaries separate.

**Tech stack:** Existing Python orchestration, saved PDF text/page markers, JSONL/CSV/Markdown artifacts and the recorded GPT judge configuration. No new inference engine or summary regeneration is required for the first stages.

**Spec:** User instructions in this chat: GPT evaluation should help prioritize human close reading; the professor's recorded requirements are summarized in `docs/meeting_20261023/next_steps_en.md`. This turn authorizes planning; it does not itself launch a new judge run.

## Existing evidence to reuse

- `docs/followup_20261020/report_en.md`: all 200 Qwen/GPT pairs received abstract-based screening; 83 selected paper pairs received independent full-article automated review. This is an enriched subset, not a human-certified population error rate.
- `docs/followup_20261020/fulltext_adjudication/`: existing full-text findings; `evidence_v2/` contains calibrated abstract-based screening. Do not mix older calibration protocols into final counts.
- `docs/gemma_evaluation_20261023/gpt_scores/`: 200 full-paper numeric judgments, including 20 major-error flags; these are scores-only suspicions without evidence quotations.
- `tools/review_summary_evidence.py` and `tools/adjudicate_summary_evidence.py`: reusable snapshot, blinding, exact-quote validation and resumable execution patterns. The latter is currently hard-coded for Qwen/GPT pairs and must not be reused for Gemma without an explicit versioned extension.
- `docs/feed_matrix_20261031/report_en.md`: 5,400 validated relevance-scoring requests. These are performance/stability results, not factuality judgments of generated summaries.

## Global constraints

- Preserve original PDFs, author abstracts, saved summaries, numeric scores and existing reviews. New corrections belong in a separate version with an edit log.
- Evaluate factual support against the same-version full article. An author abstract or another model summary is not a sufficient reference for a full-paper factuality verdict.
- No omission-only error labels. Missing evidence, unavailable supplements, extraction gaps and ambiguous interpretations remain unresolved.
- Blind candidate model labels and prior scores from the GPT reviewer; assess each candidate independently. Record the blinding map separately.
- Use a pinned available judge configuration, initially the existing recorded `gpt-6.1-sol`/medium configuration if still callable. Record the actual model identifier; a model/configuration change creates a new protocol, never a silent fallback.
- Disable browsing/tools for the judge and treat article/candidate text as data. Do not expose previous findings during a fresh independent review.
- Preserve full text where it fits; never silently truncate. Otherwise use a documented section/page retrieval procedure, recording included/omitted material and marking insufficient-coverage cases unresolved.
- Quote existence is automatically checkable; semantic interpretation and adequacy of evidence still require human judgment. Page markers refer to PDF pages, not necessarily printed journal pagination.
- Report suspected, human-confirmed, rejected and unresolved findings separately. GPT-written reference summaries are also candidates for audit, not factual ground truth.
- All new shared server artifacts receive sft group access. English reports; concise Chinese explanations for the user.

## Review focus

1. Changed source versions or PDF/summary ID mismatches invalidate reuse; freeze hashes before accepting cached work.
2. Fabricated quotations, incorrect page references or quotes from another paper must fail validation.
3. A supported sentence can still misrepresent context: check population, outcome, comparator, numbers, direction, statistical qualifiers and cellular/animal versus patient evidence.
4. A clean automated review is not certification; include independently selected, unflagged human controls and record reviewer misses.
5. Targeted/enriched selection, previous exposure and mixed generation provenance limit comparisons; use matched papers and label selection methods explicitly.

## New artifact structure

Use one root, `docs/factuality_review_20261031/` locally and `/data/SFT_demo/Oct/results/factuality_review_20261031/` on the server, with `inputs/`, `gpt_evidence/`, `human_review/` and `report_en.md`. Keep historical result trees in place and reference their exact paths/hashes.

- `inputs/manifest.json`: paper ID, candidate version/hash, PDF hash, extraction hash, prior-review source and eligibility.
- `inputs/protocol.json` and `rubric_en.md`: judge, instructions, structured schema, evidence coverage and frozen sampling rules.
- `inputs/selection.json`: calibration/control/flagged inclusion reasons and deterministic seed 42.
- `gpt_evidence/reviews.jsonl`: accepted automated findings, source locations, raw output/provenance and coverage status.
- `human_review/queue.csv`: stable finding IDs, source links, exact quotes, priority, suggested status and initially blank human verdict fields.
- `human_review/independent_pilot.csv`: human-first calibration judgments collected without GPT conclusions; preserve these separately from later adjudication.
- `report_en.md`: coverage, automated findings, independently confirmed findings, uncertainty, review costs and next decisions.

## Task 1: Inventory and a usable review queue

**Files:** Create `tools/prepare_factuality_triage.py`, `tools/export_factuality_review.py`, and focused tests in `tests/test_factuality_triage.py`. Read historical ledgers; do not modify them.

**Interfaces:** `build_manifest(sources) -> dict`; `select_review_set(manifest, seed=42) -> dict`; `export_review_queue(findings, manifest, output_path) -> None`. Every record keys on paper ID, candidate hash, source hash and protocol ID.

- [x] Verify the current 200-paper source/candidate inventory and determine whether each earlier reviewed snapshot still matches. Mark changed inputs as needing new review.
- [x] Export existing Qwen/GPT evidence to a source-linked queue. Add the 20 Gemma numeric flags as "needs evidence review", without inventing findings or treating flags as confirmed.
- [x] Create the calibration set: 10 unique papers comprising five deterministically selected Gemma-flagged cases and five randomly selected currently unflagged controls. For each, include both saved Qwen and Gemma summaries: 20 candidate reviews. Record prior exposure and selection bias.
- [x] Create a separate 20-paper random unflagged control set, disjoint from calibration and selected before the new Gemma evidence run. It tests missed flags; it is too small to certify a population error rate.
- [x] Test ID/hash mismatch rejection, deterministic sampling, no duplicate controls, stable finding IDs and empty human-verdict fields.

**Deliverable:** A readable queue and 10-paper calibration packet. Humans can begin reading before any expensive full collection rerun.

## Task 2: Calibrate evidence-backed GPT review

**Files:** Create `tools/review_summary_factuality.py`; reuse validated utilities from `tools/review_summary_evidence.py` where interfaces permit. Keep `tools/adjudicate_summary_evidence.py` historical behavior intact. Test in `tests/test_summary_factuality.py`.

**Interface:** `review_candidate(article, candidate, protocol) -> review`; `validate_review(review, supplied_input) -> review`. A review records coverage, verdict, and an array of findings containing claim type, exact candidate quote, exact article quote, PDF page/section, explanation, and major/minor/uncertain priority. Do not request speculative numerical confidence.

- [x] Freeze a rubric covering design, population, sample size, numerical results, result direction, endpoints, statistical significance, attribution, causal scope, clinical generalization and unsupported limitations. Evidence quotation alone is not a verdict.
- [x] Require `contradicted`, `unsupported_in_reviewed_material`, or `uncertain` finding status. Require quotes and a specific conflict for a contradicted finding; permit no supporting quote for absence-of-evidence statuses and retain the reviewed-coverage description instead.
- [x] Test exact quote/page provenance, wrong paper IDs, absent citations, missing tables, incomplete full-text coverage, contradictory numeric values, and a valid unsupported/uncertain case. Identical inputs resume; changed rubric/model/hash refuses reuse.
- [x] Run the 20 blinded candidate reviews from Task 1, preserving raw responses, actual judge identity, timings and any available usage metadata. Stop at this bounded stage for calibration.
- [ ] Have the user and teammate independently review the same candidates against PDFs before seeing GPT conclusions. Then compare notes and adjudicate disagreements, using PDF tables/figures when extraction is insufficient.
- [ ] Categorize GPT false alarms and misses. If the rubric changes, version it and rerun calibration; preserve earlier outputs. Expansion requires reliable evidence links and no unresolved systematic failure such as declaring abstract omissions false.

**Deliverable:** A calibrated rubric, a concrete example table and a list of cases requiring close human reading. The pilot does not establish the judge's general accuracy.

## Task 3: Extend Gemma evidence review and organize human reading

**Files:** Reuse Task 2 runner and exporter; create the new versioned run under `gpt_evidence/` and append-only human decision exports.

- [ ] With the calibrated protocol, review the complete frozen 200 Gemma summaries against source articles, reusing calibration outputs only when model, protocol and hashes match exactly. Prior numeric scores remain hidden from the judge.
- [ ] Audit every accepted finding's provenance and completion. Record partial/unavailable full text separately; never count these as clean reviews. Resume saved valid rows after quota interruptions.
- [ ] Prioritize human reading: major claim/number/direction conflicts first; uncertain evidence and extraction problems second; minor findings third. Keep GPT's label separate from the blank human decision.
- [ ] Independently inspect the preselected 20 unflagged controls without seeing GPT conclusions first. Report misses and false alarms descriptively with denominators and selection details.
- [ ] For a Qwen/Gemma comparison, use a common frozen set and the same evidence protocol for both. Reuse historical Qwen findings only as documented compatible evidence; otherwise obtain new matched reviews. Do not compare the targeted 83-paper review rate against a full 200-paper Gemma rate as if cohorts were equivalent.
- [ ] Preserve human verdict, reviewer, date, source evidence and rationale; allow confirmed error, rejected suspicion and unresolved. A second reviewer handles disputed major cases.

**Deliverable:** A complete Gemma automated screening ledger, a practical source-linked reading queue and separately labeled human decisions.

## Task 4: Report and decide the next experiment

- [ ] Report each collection's coverage, unresolved inputs, GPT-suspected issues, human-confirmed/rejected issues and human-reviewed denominators. Do not label "no issue identified" as "factually correct".
- [ ] Present 5–10 human-reviewed examples covering numbers, causal scope, safety qualifiers, source attribution, false alarms and misses. Keep unreconciled cases explicit.
- [ ] Preserve reference provenance and judge-family bias limitations. The GPT reference collection contains mixed generation provenance and is not a gold factuality standard.
- [ ] Link the separate relevance-throughput report. Do not combine its short-request rates with full-paper summary quality to claim end-to-end validated performance.
- [ ] If corrected generation is needed, create a development set from confirmed cases and a disjoint evaluation set before prompt changes; save new summaries separately and repeat evidence review on held-out cases.
- [ ] Only after this checkpoint, decide between testing full-paper generation with 9B/Gemma or multi-abstract relevance batching. Each needs its own workload-specific quality and speed evaluation.

**Deliverable:** An English evidence-backed report suitable for the next meeting, with reusable scripts and source-linked review files.

## Execution order and stopping conditions

First inventory/export, then the 10-paper calibration, then full Gemma screening and targeted/control human review, finally the English report. No automatic summary rewrite or new 200-paper generation belongs in this plan. Pause expansion for systematic evidence failures, unavailable full text or unresolved calibration problems; quota interruptions preserve progress and mark incomplete coverage. No fixed completion time is promised because judge availability and human reading determine the schedule.

Plan self-review: tasks cover source integrity, blinded evidence extraction, calibrated human review, unflagged controls, comparable cohorts and reporting limitations. This planning turn creates documentation only; no remote inference, paid API calls or source edits were performed.


## Execution checkpoint — October 31, 2026

Inventory, source-linked queue and automated calibration are complete. All 200 existing PDFs matched the historical score snapshot; all 800 current text files matched frozen hashes. Ten selected original PDFs were separately copied and verified. The final calibration covers 20 candidates and returns 13 automated concerns (12 contradicted labels and one uncertain), not human-confirmed errors. All 20 active-protocol reviews passed on their first attempt, with exact source quote/page provenance; 11 targeted software tests pass.

A real input-quality defect was found and addressed: historical PyMuPDF sort=True output interleaved the columns of paper019. Diagnostic v1/v2 results remain archived; a separate Poppler reading-order extraction feeds calibration_v3. PDF hashes and page counts remain fixed. Human interpretation remains unvalidated. Before expansion, apply/audit the corrected extraction to all 200 eligible PDFs.

`docs/factuality_review_20261031/human_review/packet_en.md` and separate reviewer CSVs are ready. Independent human calibration is the pending prerequisite; it cannot be replaced by another GPT judgment. Original summaries were not edited, and full 200-paper new Gemma evidence screening has not started. No original PDF, abstract or summary was intentionally changed.
