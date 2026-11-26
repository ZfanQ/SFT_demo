# Relevance rationale distillation readiness

## Baseline V0

The completed V0 matrix contains 400,000 Qwen grades. The model and baseline prompt were selected before the evaluator opened the 40-paper, 800-pair test reference. The evaluation was shared with the team. Codex subsequently read eight GPT grade-3 misses for a retrospective audit. The audit found four well-supported relevance disagreements and four cases where the descriptor's scope warrants review. This was an automated abstract-level review. Its findings leave the historical metrics intact. Three side-by-side semantic and Qwen Top-5 examples are available locally for the recommendation demo. [V0 results](../top50_rerank_20261123/report_en.md#november-26-full-matrix-and-held-out-evaluation)

## Prepared teaching data

The existing references already contain a grade, a verifiable abstract quote, an evidence-role label, and a short rationale. The exporter checks source hashes, paper partitions, unique pairs, score bounds, and quote presence. It exports only training rows and checks validation coverage separately. Existing source records contain abstracts and descriptor definitions. Titles can be included when available in a future frozen source.

| Pool | Pairs | Papers covered | Distinct interests |
| --- | ---: | ---: | ---: |
| Training | 480 | 24 of 128 | 344 |
| Validation | 640 | 32 of 32 | 355 |

The training sample has 282 grade-0, 52 grade-1, 23 grade-2 and 123 grade-3 targets. It provides reusable supervision with a sparse grade-2 boundary and limited paper coverage. The local JSONL export contains abstract and evidence text. The repository tracks the exporter and aggregate manifest. [Coverage manifest](coverage.json)

Run the exporter from the repository root.

```bash
python3 src/prepare_relevance_distillation.py \
  --run experiments/relevance/delivery_compact_20261125 \
  --out experiments/relevance/rationale_distillation_20261126
```

## Proposed weight-learning run

1. Keep the existing 128/32-paper development split and V0 audit separate. If the team approves weight training, add a targeted teacher packet of about eight pairs per remaining training paper, up to 832 new targets. Draw from the existing candidate ledger, prioritizing likely grade-1/2 boundaries, related but out-of-scope interests, and hard negatives. Record the sampling strata and observed grade counts. Evaluate on the original 640-pair development validation pool.
2. Run one Qwen3.5-9B QLoRA adapter on evidence-backed targets. Use the same structured input for the unadapted model and adapter so the comparison isolates weight learning. Train on assistant targets and parse the grade separately from the evidence fields. Record output tokens and inference latency. GPU24 exposes 24 GiB and has all four indexed model shards. Its current experiment environment has Torch and Transformers. PEFT, bitsandbytes and Accelerate need a compatible isolated setup before a memory check.
3. Propose a ten-minute memory and throughput check, then one formal run capped at two epochs and four GPU hours. Proceed only if the check fits the GPU and predicts completion within that budget. Stop on persistent out-of-memory, non-finite loss, or the time limit. Use a single validation checkpoint decision. Keep the simpler configuration if the adapter's balanced agreement fails to improve or its positive recall falls by more than five percentage points. The budget and operating rule are proposals for team review.
4. Before training, reserve a new paper-disjoint blind pool with a source and duplicate check against the entire 200-paper corpus. Aim for 40 newly sourced papers and 20 judged interests per paper if the team can supply them. Freeze text, catalogue, sampled pairs and hashes, and hold scores with an independent evaluator. Use the same judged pool for the model comparison after both configurations are locked. The new pool must remain outside teacher examples, rule synthesis and checkpoint selection. If a new pool is unavailable, report the comparison as development-only and keep V0 as the historical independently held-out result.

No new training or annotation jobs have been started. The team needs to confirm the weight-training scope and compute budget, and identify an approved source for the independent papers before that phase can start.
