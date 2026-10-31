# Independent Study Follow-up: Evidence Review, Short Summaries and Throughput

Date: October 20, 2026. Scope: follow-up to the October 13 meeting.

## Main findings

The two saved summary collections were screened against all 200 author abstracts. A separate, independently prompted full-article review covered 83 selected papers and both saved summary sources. The reviewer identified material errors in 51 Qwen summaries, returned no material error for 28, and left four uncertain. It identified no material errors in the 83 GPT reference summaries examined. These are automated reviewer judgments on an error-enriched subset, not a human-certified error rate or a controlled Qwen-versus-GPT model ranking.

Two independent throughput pilots produced 48 full-paper inferences. Two parallel Qwen requests improved throughput by approximately 15.4% over the paired sequential baseline. Three parallel requests consumed more memory and increased individual latency without outperforming two-way concurrency in these small runs. A five-paper revised-prompt and short-preview pilot still produced two material errors. Both were preserved, documented and corrected in a separate editorial version, which then received another full-article review.

## Existing work reused and preserved

The server contained 200 author abstracts and 200 summaries each from Qwen3-8B, GPT and Gemma. The previous GPT-6.1 Sol evaluation of Qwen was complete: mean overall score 8.082, with 37 internal major-error flags. Its protocol explicitly requested scores only, with no explanations or evidence. Those flags were used to prioritize follow-up; they are not independently established errors.

The current 200 Qwen text hashes matched the previous scoring inputs. A second server check confirmed that all 800 original text files remained unchanged during this work. No original summary, teammate score or shared directory structure was replaced. Gemma's existence was verified, but it was not included in the new evidence judgments or throughput comparison.

## Review method and coverage

1. Freeze the author abstract, Qwen and GPT text snapshots and record SHA-256 hashes.
2. Screen both candidates for each of the 200 papers against its author abstract. Randomize deterministic A/B source assignments per paper. Use separate GPT-6.1 Sol sessions, medium reasoning, with tools and browsing disabled. The reviewer does not receive source-model labels or prior numerical scores.
3. Require exact contiguous candidate and reference quotations. Reject missing/duplicate IDs, invalid mappings, fabricated quotes and changed-protocol caches. Every retained quotation was independently checked against its supplied input text by code. Quote presence establishes provenance, not the correctness of the reviewer’s interpretation.
4. Full-article follow-up includes the union of the 70 papers flagged by screening, the previous 37 score-only major-error flags, and five unflagged calibration controls: 83 unique papers in total. Both candidates are reviewed for each selected paper, rather than reviewing only the flagged source. Article text hashes were checked against metadata, and the recorded PDF and author-abstract hashes were required to match the same source version.
5. Treat abstract omissions as insufficient evidence of error. In the initial calibration, the reviewer over-enumerated details absent from the abstract; that protocol was revised and its outputs retained separately. The reported 200-paper screening uses the calibrated v2 protocol only.

The final screening produced 56 findings across 53 Qwen summaries and 24 findings across 24 GPT summaries, with overlap in affected papers. Findings include tentative discrepancies requiring the article; counts are not confirmed errors. The independent full-article pass did not see the initial findings or scores. The full-article results are:

| Saved source | Papers reviewed with article | Material error identified | No material error identified | Uncertain |
| --- | ---: | ---: | ---: | ---: |
| Qwen3-8B | 83 | 51 | 28 | 4 |
| GPT reference snapshot | 83 | 0 | 83 | 0 |

The Qwen full-article output contains 55 major, five minor and seven uncertain findings, sometimes multiple findings per summary. Of the seven uncertain findings, some accompany another definite issue in the same summary. A material-error verdict is assigned only when at least one major or minor finding is present. The reviewer’s severity is a prioritization aid, not a validated medical-risk classification.

The remaining 117 papers have abstract-based screening only. A clean screening result is not a guarantee that full-text-only mistakes are absent. The GPT reference snapshot retains its mixed provenance: 175 GPT-6.1 Sol outputs and 25 preserved teammate outputs with unverified original model/prompt. Style can still reveal candidate provenance despite label blinding, and using a GPT-family reviewer for GPT-written candidates can introduce bias.

## Concrete issues requiring attention

| Paper | Saved Qwen claim | Article evidence and interpretation |
| --- | --- | --- |
| 128 | “The study found no serious adverse events or cases of myocarditis/pericarditis.” | The article reports serious adverse events in several groups, including 3/84 in CV0701-High and 3/85 in the comparator, and states none were considered intervention-related. Removing the qualifier “vaccine-related” changes the safety claim. |
| 133 | “439,010 cases and 366,484 controls” | The article records 43,901 cases and 366,484 controls. The case count is overstated tenfold. |
| 005 | “m6A methylation of MGMT was mediated by IGF2BP2.” | The article implicates IGF2BP2 in stabilization of methylated MGMT transcripts, with direct versus indirect involvement unresolved. That differs from attributing methylation installation to IGF2BP2. |
| 079 | “The study found that adherence ... was around 64% on average” | The 64% figure is attributed in the article to a previous meta-analysis, rather than an adherence estimate from the current study. |
| 049 | The findings “were based on observational data.” | The article contains a patient prognostic component and manipulated-cell overexpression/rescue experiments. A blanket observational characterization obscures that distinction. Patient treatment efficacy remains unestablished. |

Repeated blanket statements denying causality in manipulated-cell or animal studies deserve targeted inspection. They should distinguish observed patient associations, experimental effects in the model, unvalidated pathway mediation and unproven clinical efficacy. This pattern suggests a generation-policy problem worth testing; the current results do not isolate its cause or prove that a prompt change alone solves it.

## Factual-perturbation sensitivity experiment

Three intentionally false variants were constructed in isolated experiment files. Two modify claims in the final sentence: clinical/causal overclaim in paper100 and rare-adverse-event detection/generalizability in paper128. The third asserts unproven direct binding in paper005. This tests the professor's requested principle of changing factual meaning while preserving most wording; it is not the exact literal “A is better than B” reversal.

ROUGE-1/2/L used stemming. BERTScore used roberta-large, layer 17, no IDF or baseline rescaling, slow tokenizer, CPU, and the same encoder revision as the earlier report: `722cf37b1afa9454edce342e7895e588b6ff1d59`. All candidate and reference texts in this targeted experiment fit within the encoder limit.

| Comparison to author abstract | Original BERTScore F1 | Intentionally false BERTScore F1 |
| --- | ---: | ---: |
| 005: unproven direct binding asserted | 0.85249 | 0.85235 |
| 100: final-sentence clinical and causal overclaim | 0.86687 | 0.86636 |
| 128: final-sentence rare-event detection overclaim | 0.84916 | 0.84922 |

In paper128, the false wording slightly increased the similarity score. The experiment also compared the actual saved Qwen safety statement against a minimally corrected version: BERTScore versus the author abstract changed only from 0.88122 to 0.88172. These small targeted examples demonstrate that a meaningful factual change can leave the metric nearly unchanged. They do not estimate sensitivity across all errors. Full results also preserve ROUGE scores and comparisons to the frozen GPT reference.

## Throughput experiment

The installed qwen3:8b Q4_K_M model was tested on the existing H100 MIG allocation. A private loopback Ollama server on port 11435 used the existing model files. The shared service on port 11434 and MIG configuration were not changed. Each private server was shut down after its experiment. No model download or service upgrade was performed.

Six fixed full-PDF inputs, papers 001, 002, 003, 004, 007 and 008, were extracted before timed generation. All fit the single-chunk strategy. The existing long-summary prompt and model options were reused: 32768 context, 850 output-token budget, temperature 0, seed 42, thinking disabled. Each round started a fresh private server and performed a short warm-up; loading, extraction and warm-up were excluded from the reported throughput. All measured requests had nonempty outputs, normal completion and at most 250 words. These checks do not certify factual accuracy.

Two ABBA sequences were run: concurrency 1–2–2–1 and 1–3–3–1. Each row below aggregates its two six-paper rounds. Throughput is total completed papers divided by total timed wall duration, not the mean of per-request token speeds.

| Pilot | Concurrent requests | Inferences | Papers/minute | Median request latency, seconds | Peak sampled GPU memory, MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1–2–2–1 | 1 | 12 | 3.300 | 17.74 | 9,795 |
| 1–2–2–1 | 2 | 12 | 3.810 | 28.85 | 14,412 |
| 1–3–3–1 | 1 | 12 | 3.260 | 17.75 | 9,795 |
| 1–3–3–1 | 3 | 12 | 3.729 | 46.01 | 18,887 |

Two-way throughput improved by approximately 15.4% against its paired sequential runs; three-way improved by approximately 14.4% against its own baseline. Two-way concurrency is the more promising next operating candidate for this workload. This is a small, repeated six-paper pilot, not proof of an optimum or of performance on multi-chunk papers. Batch position and prefix-cache behavior can influence timing. The GPU reports compute utilization as N/A, so memory occupancy is not described as compute utilization or GPU saturation. Increased concurrency also increases per-request latency. The saved raw responses permit later output-quality comparisons; concurrency-dependent factual quality has not been established.

## Revised long and short-summary development pilot

Five error-enriched development cases, papers 005, 012, 049, 100 and 128, were generated under a revised long-summary prompt addressing evidence setting, causal scope, molecular roles and safety qualifiers. Each short preview was generated from the new longer summary and constrained to two or three sentences. Original collection files remained untouched.

Long outputs contained 160–241 words; one was below the requested 180–220 target but still below the hard 250-word maximum. Short previews contained 50–68 words and passed the implemented sentence/length checks. Independent full-article review nevertheless found:

- Paper049's longer output reversed the PGM5P4-AS1 direction in its conclusion, stating that it promotes progression despite earlier describing suppression of malignant behavior.
- Paper128's short preview stated that both investigational vaccines produced dose-dependent antibody and T-cell responses, although CV0601 was tested at only one dose and the reported dose-dependent neutralizing response concerned CV0701.

The other four longer and four shorter outputs received no material-error finding in that pass. This is not sufficient reliability for an automatic 200-paper short-summary rollout.

A separate editorial development version corrects those two claims with a change log and source evidence. A fresh full-article pass of all five long/short pairs identified no material errors in that edited version. Those outputs must be labeled edited, not raw Qwen performance or held-out model improvement. They are useful review examples, not production approval. Formal user usefulness and readability comparisons have not yet been completed.

## Personalized-feed experiment: prepared, not evaluated

A versioned SciCommons PubMed API snapshot was saved, with artifact version `2026-10-20T02:11:08+00:00`. Fifty records with titles and abstracts were deterministically selected from the first 100 returned records for site availability date October 20. This is a pilot candidate pool, not the complete daily PubMed feed and not a publication-date sample. Twenty synthetic interest profiles were prepared. No real user accounts were created and no site preferences were changed.

The existing semantic ranker's implementation could not be located in the inspected local project or known server project directories. The user did not recall its location. Public page/OpenAPI probes were forbidden while the articles endpoint was readable. No replacement algorithm is claimed to reproduce the teammate's baseline, and no ranking comparison is reported. The next ranking experiment needs the actual baseline implementation and settings, a shared candidate pool, Qwen rankings and independent relevance judgments.

## Reproducibility, limitations and next actions

Artifacts on GPU24: `/data/SFT_demo/Oct/results/followup_20261020/`. Earlier standalone throughput, sensitivity and revised-pilot folders are retained as source runs. The follow-up package includes input manifests, exact prompts, schemas, model/effort records, per-batch usage and session IDs, quoted findings, source hashes, raw experiment results and editorial changes. Eight validation tests cover wrong/duplicate mappings, fabricated or noncontiguous quotations, inconsistent verdicts and duplicate writer protection. All retained evidence quotations and aggregate counts were independently recomputed from saved inputs.

This work completes the 200-paper abstract screening and the defined 83-paper targeted full-text follow-up. It does not complete a 200-paper full-text factual certification, a human blinded review, all-model quality comparison, held-out validation, production deployment, or the semantic-ranking comparison. The next useful steps are to adjudicate disputed findings with student review, complete full-text coverage of the remaining 117 if comprehensive factual coverage is required, test the revised generation policy on separate development/held-out cases, and obtain the real semantic-ranking baseline. Original long summaries should remain frozen for evaluation; edited versions need new identifiers.
