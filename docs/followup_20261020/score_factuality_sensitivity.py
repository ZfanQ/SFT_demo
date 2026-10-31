#!/usr/bin/env python3
"""Measure similarity sensitivity to explicitly labeled factual perturbations."""
import argparse
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    args.output.mkdir(exist_ok=False)
    args.output.chmod(0o2775)
    os.umask(0o002)
    os.environ.update(HF_HOME="/data/SFT_demo/.cache/huggingface", HF_HUB_OFFLINE="1",
                      TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    import torch
    from bert_score import BERTScorer
    from rouge_score import rouge_scorer
    torch.set_num_threads(4)
    scorer = BERTScorer(model_type="roberta-large", num_layers=17, lang="en", idf=False,
                       rescale_with_baseline=False, use_fast_tokenizer=False,
                       device="cpu", batch_size=1, nthreads=4)
    expected = "722cf37b1afa9454edce342e7895e588b6ff1d59"
    if getattr(scorer._model.config, "_commit_hash", None) != expected:
        raise ValueError("Wrong encoder checkpoint")
    rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    cases = json.loads(args.input.read_text())
    rows = []
    for case in cases:
        for variant, text in case["variants"].items():
            for ref, reference in case["references"].items():
                text, reference = " ".join(text.split()), " ".join(reference.split())
                row = {"case": case["case"], "paper_id": case["paper_id"], "variant": variant,
                       "reference": ref, "synthetic": case["synthetic"],
                       "candidate_tokens": len(scorer._tokenizer.encode(text, add_prefix_space=True)),
                       "reference_tokens": len(scorer._tokenizer.encode(reference, add_prefix_space=True))}
                for metric, value in rouge.score(reference, text).items():
                    row[metric + "_f1"] = value.fmeasure
                with torch.inference_mode():
                    _, _, f = scorer.score([text], [reference], batch_size=1)
                row["bertscore_f1"] = float(f[0])
                rows.append(row)
    report = {"cases": cases, "rows": rows, "encoder_revision": expected,
              "bertscore_hash": scorer.hash, "scope": "Targeted illustrative controls, not an error-rate estimate or a general benchmark.",
              "warning": "Synthetic counterfactuals are intentionally false, isolated experimental data; never production summaries."}
    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(rows, indent=2), flush=True)


if __name__ == "__main__":
    main()
