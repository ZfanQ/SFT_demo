#!/usr/bin/env python3
"""Create the English report from independently verified expanded matrix analyses."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    args=p.parse_args();root=args.root;results=[]
    for label,name in [('qwen3_8b','Qwen3-8B'),('qwen35_9b_llamacpp','Qwen3.5-9B'),('gemma4_12b_llamacpp','Gemma-4-12B')]:
        path=root/label/'analysis.json'
        if path.exists():results.append((label,name,json.loads(path.read_text())))
    if not results:raise ValueError('No verified results')
    dataset=json.loads((root/'dataset.json').read_text());dataset_hash=sha(root/'dataset.json')
    assert all(x['dataset_sha256']==dataset_hash for _,_,x in results)
    full=all(x['state']=='verified_complete' for _,_,x in results) and len(results)==3
    lines=['# Medical Feed Concurrency Matrix: 200 Abstracts and Three Interest Profiles','',
           'Date: October 31, 2026.','',
           '## Scope and completion','',
           f'This report contains {sum(x["timed_requests"] for _,_,x in results):,} independently verified timed requests across {len(results)} model configurations. '
           'Each complete model run covers 200 frozen author abstracts, three profiles and requested concurrency 2/4/8: 600 distinct paper/profile inputs and 1,800 timed requests. '
           +('All three model matrices are complete.' if full else 'The model matrix is not yet complete; coverage below must not be presented as a completed three-model comparison.'),'',
           'This is independent-abstract relevance scoring, not full-paper summarization. The protocol permits model-upgrade stages only after the Qwen3-8B matrix is complete and independently verified. '
           'The experiment measures throughput, latency, GPU-layer offload and output/score stability. There are no independently established relevance gold labels.','',
           '## Combined throughput and latency','',
           '| Model | Backend | Concurrent requests | Profiles | Timed requests | Paper/profile scores per min | Median latency (s) | p95 latency (s) | Peak sampled memory (MiB) | Output tokens/s |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for _,name,r in results:
        for g in r['aggregates']:
            backend=r.get('backend',{}).get('backend','ollama')
            lines.append(f'| {name} | {backend} | {g["parallel"]} | {g["profiles"]} | {g["requests"]} | {g["documents_per_minute"]:.2f} | '
                         f'{g["median_latency_s"]:.3f} | {g["p95_latency_s"]:.3f} | {g["peak_sampled_memory_mib"]:.0f} | {g["output_tokens_per_second"]:.2f} |')
    lines+=['','Throughput is total completed requests divided by summed timed durations, not a mean of per-round rates. '
            'One request scores one paper for one profile; the unit is paper/profile scores per minute, not unique papers already evaluated for all profiles. '
            'Each profile contributes the same 200 articles. For example, scoring every candidate for 20 profiles requires 20 requests per candidate in this pointwise design. '
            'Latency runs from worker request-path start to receipt of the decoded response, including request preparation, service queuing and inference; '
            'it excludes output validation, ledger writing and time an item waits in the upstream dataset before a worker is free. This is a saturated closed-loop load test, not a real-user arrival simulation. '
            'Output-token rates depend on each model\'s tokenizer and do not represent equal amounts of semantic content across models.','',
            '## Throughput candidates','']
    if full and (root/'throughput_latency.png').exists():
        lines+=['![Throughput and active-request latency](throughput_latency.png)','',
                'Each point aggregates 600 requests. The curve labels are concurrency settings; higher throughput and lower latency are preferable, '
                'subject to relevance quality. Both upgraded models use a direct llama.cpp backend; the 8B configuration uses Ollama.','']
    for _,name,r in results:
        if r['state']!='verified_complete':continue
        best=max(r['aggregates'],key=lambda x:x['documents_per_minute']);baseline=next(x for x in r['aggregates'] if x['parallel']==2)
        gain=(best['documents_per_minute']/baseline['documents_per_minute']-1)*100
        lines.append(f'- {name}: highest observed throughput at **{best["parallel"]} requests**, **{best["documents_per_minute"]:.2f} paper/profile scores/minute**, '
                     f'**{gain:+.1f}%** against its 2-request baseline; p95 latency **{best["p95_latency_s"]:.3f} s**. Rates count paper/profile scores. This is a candidate, not an established optimum.')
    lines+=['','For a latency-aware next validation, concurrency 4 is a reasonable candidate in these configurations:','',
            '| Model | Throughput gain: 4 to 8 | p95 latency at 4 (s) | p95 latency at 8 (s) |',
            '| --- | ---: | ---: | ---: |']
    for _,name,r in results:
        groups={g['parallel']:g for g in r['aggregates']}
        if 4 in groups and 8 in groups:
            a,b=groups[4],groups[8]
            lines.append(f'| {name} | {(b["documents_per_minute"]/a["documents_per_minute"]-1)*100:+.1f}% | {a["p95_latency_s"]:.3f} | {b["p95_latency_s"]:.3f} |')
    lines+=['','This is a throughput/latency tradeoff, not a production choice or evidence of improved relevance. No deployment latency target was supplied.']
    lines+=['','### Illustrative workload arithmetic','',
            'The meeting mentioned 10,000 incoming abstracts/day and earlier discussion considered about 20 profiles. '
            'These are illustrative workload assumptions, not a verified PubMed arrival rate or a measured deployment requirement. '
            'Pointwise scoring would require 200,000 requests. At each configuration\'s highest observed throughput, the arithmetic is:', '',
            '| Model | Selected concurrency | Hours for 200,000 scores |',
            '| --- | ---: | ---: |']
    for _,name,r in results:
        best=max(r['aggregates'],key=lambda x:x['documents_per_minute'])
        lines.append(f'| {name} | {best["parallel"]} | {200000/best["documents_per_minute"]/60:.1f} |')
    lines+=['','This is an extrapolation, not a capacity forecast: it assumes unchanged input lengths, profile mix, model behavior, '
            'continuous availability and observed service rate. It excludes feed retrieval, summarization and other pipeline work. '
            'It motivates testing semantic prefiltering or multiple abstracts per prompt as separate experimental axes.','',
            'Selecting an operating point requires a latency target, memory reserve and acceptable relevance quality. '
            'A larger configured request count is not a quality improvement or evidence of full GPU utilization. '
            'Within-profile concurrency comparisons are controlled for the input workload; comparisons across models include architecture, quantization and template differences.','',
            '## Per-profile rounds','',
            '| Model | Profile | Concurrent requests | Valid / expected | Scores/min | p95 latency (s) |',
            '| --- | --- | ---: | ---: | ---: | ---: |']
    for _,name,r in results:
        for g in r['rounds']:
            lines.append(f'| {name} | {g["profile_id"]} | {g["parallel"]} | {g["valid"]} / 200 | {g["documents_per_minute"]:.2f} | {g["p95_latency_s"]:.3f} |')
    lines+=['','Observed input-token ranges, including instructions/profile and source-specific templates:','',
            '| Model | Minimum | Maximum |', '| --- | ---: | ---: |']
    for _,name,r in results:
        lines.append(f'| {name} | {min(x["input_tokens_min"] for x in r["rounds"])} | {max(x["input_tokens_max"] for x in r["rounds"])} |')
    lines+=['','## Ordinal-score and ranking stability','',
            'Each request returns only the article ID, profile ID and an integer relevance score: 0 unrelated, 1 peripheral, 2 relevant, 3 directly relevant. '
            'The table compares each model with its own 2-request outputs. Correlation uses average ranks for ties; '
            'no arbitrary article-ID tie-breaking is used to manufacture a top-k ranking. Threshold flips cross the boundary between scores below 2 and scores at least 2.','',
            '| Model | Profile | Parallel vs 2 | Exact score agreement | Mean absolute score change | Relevant/not-relevant flips | Spearman (tied ranks) |',
            '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for _,name,r in results:
        for g in r['stability_vs_p2']:
            corr=f'{g["tied_rank_spearman"]:.4f}' if g['tied_rank_spearman'] is not None else 'undefined (constant scores)'
            lines.append(f'| {name} | {g["profile_id"]} | {g["parallel"]} | {g["exact_agreement"]:.1%} | {g["mean_absolute_difference"]:.3f} | {g["relevant_threshold_flips"]} / 200 | {corr} |')
    lines+=['','### Score distributions at concurrency 2','',
            '| Model | Profile | Score 0 | Score 1 | Score 2 | Score 3 |',
            '| --- | --- | ---: | ---: | ---: | ---: |']
    for _,name,r in results:
        for d in r.get('score_distributions',[]):
            if d['parallel']==2:
                c=d['counts'];lines.append(f'| {name} | {d["profile_id"]} | {c["0"]} | {c["1"]} | {c["2"]} | {c["3"]} |')
    lines+=['','Class imbalance can inflate exact agreement; the distributions above are model outputs, not validated class frequencies. '
            'A changed score is not necessarily a worse score, and stable scores can still be wrong. '
            'There is one measured pass per paper/profile/concurrency cell; this expanded experiment does not separately estimate repeated-run variability at the same concurrency. '
            'The three profile orders balance configuration position, but profile-specific workloads are not interchangeable timing repetitions. '
            'Claims of improved ranking quality require independently judged relevance and comparison with the actual semantic-ranking baseline.','',
            '## Reproducible protocol','',
            '- Frozen inputs: all 200 existing abstracts; three synthetic researcher-interest profiles (oncology, cardiovascular medicine, neuroscience), not real-user preference histories; seed-42 article order reused for all configurations and models. This historical collection is not a fresh one-day PubMed feed or a demonstrated daily production workload.',
            '- Profile-specific concurrency order: oncology 2–4–8, cardiovascular 4–8–2, neuroscience 8–2–4.',
            '- Common request options: 4,096-token context, 96-token output cap, temperature 0, seed 42, thinking disabled. The upgraded-model aliases explicitly match the old Qwen effective presence/repetition penalties and top-k/top-p/min-p settings; source-specific templates and stop tokens remain intact.',
            '- Warmup: 2 × concurrency synthetic held-out abstract requests at the target concurrency, excluded from timing. Every timed round starts a fresh private service on loopback port 11437.',
            '- Timings exclude input preparation, standalone preflight tokenization, server startup, model load and warmup. Request-path template rendering/tokenization remains included. They include HTTP handling, queuing, inference, validation and serialized raw-ledger writes. Prefix caching remains enabled.',
            '- Each accepted round must contain exactly 200 unique article/profile records, valid structured scores and normal completion. Failed or interrupted attempts remain stored and are excluded from accepted-round aggregates.',
            '- Independent validation re-parses raw responses, checks input hashes and token budget, recomputes all timing aggregates, verifies full GPU-layer offload and inspects measured overlapping execution slots in backend logs.',
            '- The GPU is the existing H100 MIG/vGPU allocation, not an unrestricted full H100. Compute-utilization telemetry is unavailable; approximately one-second memory samples must not be relabeled as compute utilization. Full transformer-layer offload does not mean every tensor or buffer is GPU-resident; host buffers are preserved in backend memory logs. Other GPU work and changes outside shared-service checks cannot be entirely ruled out.',
            '- Original abstracts are hash-checked after each complete model. Existing summary files are not inputs or outputs of this experiment. Shared Ollama service settings are preserved.',
            '', '## Model provenance','',
            '| Report label | Registered model / source reference | Quantization | Model digest |',
            '| --- | --- | --- | --- |']
    provenance_notes=[]
    for label,name,r in results:
        m=r['model'];lines.append(f'| {name} | `{m["name"]}` | {m["details"]["quantization_level"]} | `{m["digest"]}` |')
        setup=root/f'{label}_model_setup.json'
        if setup.exists():
            source=json.loads(setup.read_text())['source']
            provenance_notes.append(f'{name} source checkpoint: `{source["name"]}`, digest `{source["digest"]}`.')
    lines+=['',*provenance_notes,'',
            'Qwen3.5-9B native Ollama 0.34.4 preflight requested two slots but the scheduler forced one for the `qwen35` architecture. '
            'That attempt was stopped before timed requests and remains preserved. The successful comparison uses a separately labeled direct llama.cpp backend reading the same checkpoint, '
            'with the official pinned HF chat template and tokenizer. Each round checks a representative rendered prompt for exact token-ID parity with the GGUF server; full GPU-layer offload and per-slot context are also checked. '
            'No Ollama blocklist or installed binary was patched. Consequently, 8B-versus-9B speed differences combine model and frontend/renderer differences; they do not isolate a model-upgrade effect. '
            'The initial failed CPU-discovery probe and corrected context-log parser probe are excluded, as is the eight-request successful smoke test. '
            '[Compatibility evidence](compatibility_notes_en.md) records the sequence.','',
            'Gemma-4-12B uses the separately labeled direct llama.cpp text-only backend after the original Ollama engine stalled during empty-input initialization, before timed requests. The direct configuration disables that default empty-input warmup and uses the embedded GGUF template/tokenizer with thinking off; common synthetic request warmups are still performed and excluded. All 200 prompts per round are checked for preserved system/user text and context budget. Independent official-HF tokenizer parity was not established for Gemma. The successful workaround changes frontend and text-only initialization together; the precise kernel cause of the original stall was not isolated. '
            'This Q4_K_M Gemma run is a new configuration, separate from the teammate historical HF bitsandbytes NF4 full-paper-summary run. These abstract-relevance outputs must not be combined with the historical summary ROUGE/BERTScore or GPT accuracy tables.','',
            '## Audit files and remaining work','',
            f'Dataset SHA-256: `{dataset_hash}`.','',
            'Per-model `analysis.json` contains verified per-profile and combined measurements, engine evidence and the complete score-variation list. '
            'Each round retains its model-residency snapshot, server log, warmup responses, timed JSONL responses, GPU samples and status. '
            'Source checkpoints, alias settings, inherited model metadata and exact script hashes are preserved.','',
            'Next, assess relevance on a preselected independently reviewed sample, inspect concurrency-dependent score changes, and compare final ranking with the identified existing semantic baseline. '
            'At a fixed GPU concurrency, test several abstracts per prompt separately, with stable article IDs and cross-batch anchor checks. Only then choose a production configuration. Full-paper summarization needs a separate long-context/long-output benchmark.','',
            'Server experiment root: `/data/SFT_demo/Oct/results/feed_matrix_20261031/`.']
    (root/'report_en.md').write_text('\n'.join(lines)+'\n')
    print('Wrote English report; full three-model coverage:',full)


if __name__=='__main__':main()
