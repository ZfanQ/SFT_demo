# Qwen3-8B: two-reference ROUGE / BERTScore

The same 200 saved candidates were scored against two frozen reference sets. No model summaries were generated or changed.

| Reference | ROUGE papers | R1 F1 | R2 F1 | RL F1 | BERTScore papers | BERTScore F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| author_abstract | 200 | 0.6310 | 0.3844 | 0.4418 | 200 | 0.9033 |
| gpt_reference | 200 | 0.4702 | 0.1384 | 0.2552 | 200 | 0.8713 |

Scores are mean per-paper F1 on a 0–1 scale; BERTScore is unrescaled.
BERTScore: roberta-large, layer17, IDF off, CPU. ROUGE: stemming on.
ROUGE uses complete texts. Standard BERTScore uses at most512 tokens including special tokens. Every affected pair is flagged in CSV/JSON.
Cross-reference matched BERTScore subset: 189 papers; aggregates are in summary.json.
Author abstracts retain their published section labels and registration text. Only whitespace was normalized.
GPT references are the pre-existing 200-file snapshot, with mixed generation provenance; a teammate's newer output is a separate reference version.
Files changed outside this frozen run during scoring: 0. Results still refer only to the saved snapshot.
Overlap/semantic similarity metrics are not an independent full-paper factuality assessment.
