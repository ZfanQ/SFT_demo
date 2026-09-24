# Local Paper Summarization

## Model and workflow

- **Model:** Qwen3-8B (`qwen3:8b`), running locally through Ollama.
- **Settings:** thinking off, temperature 0, seed 42, maximum context 28,000 tokens.
- **Evaluation:** ROUGE-1/2/L and BERTScore (RoBERTa-large, layer 17), compared with teacher-generated references. Only the reference word count is given to Qwen, never the reference text.

## Run all five papers

Start Ollama first, then run:

```bash
cd /Users/Documents/Summarize_LLM_SFT/local_test
../.venv/bin/python qwen_eval.py all
```

This extracts the PDFs, generates summaries, and calculates the scores.
## Results

| Model | R1 | R2 | RL | BERTScore |
| --- | ---: | ---: | ---: | ---: |
| Base | 0.4918 | 0.1700 | 0.2771 | 0.8817 |

Base = qwen3:8b. Mean F1 scores (0-1); scored 5/5 papers.

## Files

| File | Purpose |
| --- | --- |
| `qwen_eval.py` | Python pipeline |
| `paper_001.pdf` to `paper_005.pdf` | Original papers |
| `paper_XXX_reference.txt` | Teacher-generated reference summaries |
| `paper_XXX_qwen.txt` | Original Qwen-generated summaries |
| `outputs/results.md` | Mean F1 table: Model, R1, R2, RL, BERTScore; includes the scored-paper count |
| `.extraction/` | Hidden cache of extracted paper text |
| `README.md` | This guide |
