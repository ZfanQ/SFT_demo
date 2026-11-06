# Gemma summaries scored by GPT-6.1 Sol

This is a separate scores-only evaluation of 200 saved Gemma summaries against complete extracted original PDFs. Candidate summaries and PDFs are unchanged. The rubric is the historical Qwen scores-only rubric with the candidate name replaced by Gemma. Model: gpt-6.1-sol; medium reasoning; independent ephemeral session per paper, no tools or browsing. Requests may run concurrently, while result writes and exports are serialized. No other candidate or prior scores are supplied.

Scores use 1–10 accuracy/coverage/clarity/conciseness, with weights 50/25/15/10 percent. A major-factual-error flag requires accuracy <=4 and caps the weighted total at 5. Overall scores are rounded to one decimal. These numeric judgments are not quote-backed error adjudication or human certification.

inputs.json records source hashes and extraction counts. Local source_pairs.jsonl supplies the same frozen full-PDF input; its compressed snapshot remains on the server. evaluations.jsonl preserves scores, flag, judge metadata and usage. scores.csv and statistics.json are regenerated from accepted records. status.json distinguishes completed, partial and blocked states. Re-running the evaluator with unchanged inputs/rubric resumes existing records. Never mix a modified rubric or summary into this run.

Execution uses the Mac's existing Codex login. It does not copy credentials. Original Qwen results remain in Oct/GPT_eval. Detailed metric results are in Oct/results/gemma_dual_reference_metrics_20261023.
