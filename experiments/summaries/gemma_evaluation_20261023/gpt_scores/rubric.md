# Gemma paper-summary evaluation rubric (version 2: scores only)

Judge: GPT-6.1 Sol (`gpt-6.1-sol`), medium reasoning, one independent session per paper.
Reference: the complete extracted text of the original PDF, including tables when extractable.
Candidate: the uncorrected Gemma summary, supplied verbatim. No GPT reference summary is used.

Score each criterion from 1.0 to 10.0; decimal values are allowed (prefer one decimal place).

- **Accuracy (50%)**: factual support, correct numerical results and outcome definitions,
  population/design/methods, uncertainty, association versus causation, and absence of invented claims.
- **Coverage (25%)**: the main objective, design/method, population/data, principal findings,
  conclusion and relevant limitations. Judge selection under the 250-word budget; not every detail
  or number is required. Do not reward inclusion of less important details over central findings.
- **Clarity (15%)**: coherent, readable, self-contained English; clear entities and scientific terms;
  no ambiguity that changes the intended scientific meaning.
- **Conciseness (10%)**: useful information density, little repetition or filler, one paragraph,
  and compliance with the maximum 250-word requirement. Shortness alone is not a weakness.

Calibration anchors, applied consistently:
- 9–10: exceptionally accurate and informative, no material defect; reserve 10 for near-perfect work.
- 7–8.9: strong summary with minor omissions or small inaccuracies.
- 5–6.9: usable but with material gaps, ambiguous interpretation or noticeable errors.
- 3–4.9: substantial misrepresentation, major factual errors, or poor coverage of central findings.
- 1–2.9: largely incorrect, unrelated or misleading about the study's central message.

A **major factual error** changes a central result, interpretation, population, design, outcome,
or causal/clinical meaning; major numerical misinterpretations also qualify. When present,
accuracy must be <=4 and the overall score is capped at 5. A minor factual issue is peripheral
and does not materially change the study's interpretation. Important omissions belong in
key_omissions; they do not require inventing an unsupported summary claim.

Overall score = 0.50*accuracy + 0.25*coverage + 0.15*clarity + 0.10*conciseness,
with the major-error cap, rounded to one decimal. The script computes this score transparently.
Return only the four numeric component scores and paper ID, plus a boolean
major_factual_error for the overall cap. Do not output comments, rationale, evidence quotations,
issues, omissions, suggestions or rewritten summaries. Assess all facts and central omissions
against the full paper internally before scoring. No outside knowledge is needed.
These are automated model judgments, not ground-truth or a blinded human factuality review.
