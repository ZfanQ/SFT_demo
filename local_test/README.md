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

## GPU24 follow-up pilot

The separate [GPU24 Qwen3-8B versus Qwen3-14B result](../docs/gpu24-qwen-baselines-2026-09-28.md) reports a five-paper full-text rerun on 2026-09-28. Its scores belong to that run and do not replace the local results above.

## Gemma / Llama on H100

See [the CUDA evaluation guide](README_Gemma_Llama.md) for `Gemma_Llama_eval.py`, which evaluates Gemma 4 12B IT and Llama 3.1 8B Instruct on the same five papers and writes a separate results README with R1, R2, RL and BERTScore. This pipeline has not yet been run on the server.
