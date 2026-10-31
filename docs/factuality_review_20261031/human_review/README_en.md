# Human Calibration Instructions

Start with `packet_en.md` and the linked original PDFs. Save a separate copy of `independent_pilot.csv` per reviewer before entering decisions. Do not open the GPT findings, report, model mapping or historical flags first; if you already saw them, record that exposure in the reason field.

Each row is one candidate summary, not one article or one finding. Read the whole summary against the source article, including the relevant tables/figures. Record one of `material_error_identified`, `no_issue_identified` or `uncertain` in `human_verdict`. A no-issue judgment is limited to your review and does not certify correctness. Enter your name and review date. For any suspected error, enter the candidate quote, PDF page, source quotation and reason. If more than one issue exists, describe them in an accompanying notes file keyed by paper/candidate ID.

Two reviewers should initially work independently. Afterward compare judgments, then inspect GPT findings using `queue.csv`. The queue has one row per automated finding or old numeric flag; it is deliberately separate from the human-first summary judgments. For each queue row use `confirmed_error`, `rejected_suspicion` or `unresolved`; add your reason, source evidence and reviewer/date. Do not mark all rows for a paper confirmed merely because one error exists.

An empty cell means unreviewed. A blank or zero PDF page in an automated finding means evidence was not localized; do not invent a location. Major/minor are the model's priorities and require human confirmation. Historical numeric flags and newer quote-backed findings may refer to the same issue and must not be counted twice.

Before expanding the new protocol to all 200 papers, reconcile substantive disagreements, inspect any automated false alarms/misses, and record whether the reviewer systematically mishandles numbers, causal language or missing evidence. The 10-paper calibration is enriched and cannot estimate the collection's overall factual error rate.

The separate 20 historically unflagged control papers are reserved in the selection manifest. They should be independently read without new GPT conclusions, following the same procedure, when the calibrated protocol is expanded.
