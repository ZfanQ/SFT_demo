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
           '## Findings','']
    if full:
        _,leader_name,leader,peak=max(
            [(label,name,r,g) for label,name,r in results for g in r['aggregates']],
            key=lambda item:item[3]['documents_per_minute'])
        four=next(g for g in leader['aggregates'] if g['parallel']==4)
        lines+=[f'{leader_name} achieved the highest measured throughput: **{peak["documents_per_minute"]:.2f} paper/profile scores/minute** '
                f'at concurrency {peak["parallel"]}. At concurrency 4, it processed **{four["documents_per_minute"]:.2f} scores/minute** '
                f'with p95 latency **{four["p95_latency_s"]:.3f} s**, compared with **{peak["p95_latency_s"]:.3f} s** at the throughput maximum.','']
    lines+=[
           f'The benchmark evaluated {sum(x["timed_requests"] for _,_,x in results):,} independently verified timed requests across {len(results)} model configurations. '
           'Each complete matrix scores 200 frozen abstracts for three research-interest profiles at concurrency 2, 4 and 8: 600 distinct paper/profile inputs and 1,800 timed requests per model. '
           +('All three matrices are complete.' if full else 'The tables report the completed coverage available so far.'),'',
           'The experiment measures the throughput, latency, GPU-layer offload and score stability of independent-abstract relevance scoring. '
           'The Qwen3-8B matrix was completed and verified before the upgraded-model stages.','',
           '## Combined throughput and latency','',
           '| Model | Backend | Concurrent requests | Profiles | Timed requests | Paper/profile scores per min | Median latency (s) | p95 latency (s) | Peak sampled memory (MiB) | Output tokens/s |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for _,name,r in results:
        for g in r['aggregates']:
            backend=r.get('backend',{}).get('backend','ollama')
            lines.append(f'| {name} | {backend} | {g["parallel"]} | {g["profiles"]} | {g["requests"]} | {g["documents_per_minute"]:.2f} | '
                         f'{g["median_latency_s"]:.3f} | {g["p95_latency_s"]:.3f} | {g["peak_sampled_memory_mib"]:.0f} | {g["output_tokens_per_second"]:.2f} |')
    lines+=['','Throughput is total completed requests divided by summed timed durations, expressed as paper/profile scores per minute. '
            'Each request scores one paper for one profile; each profile contributes the same 200 articles. '
            'Latency runs from worker request-path start to receipt of the decoded response, including request preparation, service queuing and inference; '
            'output validation, ledger writing and waiting for a free client worker fall outside that latency measurement.','',
            '## Throughput and latency tradeoff','']
    if full and (root/'throughput_latency.png').exists():
        lines+=['![Throughput and active-request latency](throughput_latency.png)','',
                'Each point aggregates 600 requests; labels give concurrency. Qwen3-8B uses Ollama and both upgraded models use direct llama.cpp.','']
    for _,name,r in results:
        if r['state']!='verified_complete':continue
        best=max(r['aggregates'],key=lambda x:x['documents_per_minute']);baseline=next(x for x in r['aggregates'] if x['parallel']==2)
        gain=(best['documents_per_minute']/baseline['documents_per_minute']-1)*100
        lines.append(f'- {name}: highest observed throughput at **{best["parallel"]} requests**, **{best["documents_per_minute"]:.2f} paper/profile scores/minute**, '
                     f'**{gain:+.1f}%** against its 2-request baseline; p95 latency **{best["p95_latency_s"]:.3f} s**.')
    lines+=['','Concurrency 4 offers a practical throughput/latency balance for the next relevance-quality evaluation. '
            'Moving to 8 produces a modest throughput gain while nearly doubling p95 latency:','',
            '| Model | Throughput gain: 4 to 8 | p95 latency at 4 (s) | p95 latency at 8 (s) |',
            '| --- | ---: | ---: | ---: |']
    for _,name,r in results:
        groups={g['parallel']:g for g in r['aggregates']}
        if 4 in groups and 8 in groups:
            a,b=groups[4],groups[8]
            lines.append(f'| {name} | {(b["documents_per_minute"]/a["documents_per_minute"]-1)*100:+.1f}% | {a["p95_latency_s"]:.3f} | {b["p95_latency_s"]:.3f} |')
    lines+=['','Use concurrency 8 when batch completion rate has priority; evaluate concurrency 4 when individual response time also matters. '
            'Final selection depends on the application\'s latency target and independently assessed relevance quality.']
    lines+=['','### Illustrative workload arithmetic','',
            'The meeting\'s illustrative scenario of 10,000 abstracts/day and about 20 profiles requires 200,000 pointwise scoring requests. '
            'Applying each configuration\'s highest observed throughput gives:', '',
            '| Model | Selected concurrency | Hours for 200,000 scores |',
            '| --- | ---: | ---: |']
    for _,name,r in results:
        best=max(r['aggregates'],key=lambda x:x['documents_per_minute'])
        lines.append(f'| {name} | {best["parallel"]} | {200000/best["documents_per_minute"]/60:.1f} |')
    lines+=['','This extrapolation assumes the measured input-length/profile mix, service rate and continuous availability; '
            'feed retrieval, summarization and other pipeline work require additional time. The arrival volume is a scenario from the discussion. '
            'The estimates motivate testing semantic prefiltering and multiple abstracts per prompt.','',
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
            'The table compares each model with its own 2-request outputs. Spearman correlation uses average ranks for ties. '
            'Threshold flips cross the boundary between scores below 2 and scores at least 2.','',
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
    lines+=['','These distributions show how each model uses the relevance scale. Class imbalance can raise exact agreement; '
            'interpret it together with threshold flips and tied-rank correlation.','',
            '## Reproducible protocol','',
            '- Frozen inputs: all 200 existing abstracts and three synthetic researcher-interest profiles (oncology, cardiovascular medicine, neuroscience). The seed-42 article order is reused across configurations and models.',
            '- Profile-specific concurrency order: oncology 2–4–8, cardiovascular 4–8–2, neuroscience 8–2–4.',
            '- Common request options: 4,096-token context, 96-token output cap, temperature 0, seed 42, thinking disabled. The upgraded-model aliases explicitly match the old Qwen effective presence/repetition penalties and top-k/top-p/min-p settings; source-specific templates and stop tokens remain intact.',
            '- Warmup: 2 × concurrency synthetic held-out abstract requests at the target concurrency, excluded from timing. Every timed round starts a fresh private service on loopback port 11437.',
            '- Timed-round throughput includes request-path template rendering/tokenization, HTTP handling, queuing, inference, validation and serialized raw-ledger writes. Input preparation, standalone preflight tokenization, server startup, model load and warmup are excluded. Prefix caching remains enabled.',
            '- Each accepted round must contain exactly 200 unique article/profile records, valid structured scores and normal completion. Failed or interrupted attempts remain stored and are excluded from accepted-round aggregates.',
            '- Independent validation re-parses raw responses, checks input hashes and token budget, recomputes all timing aggregates, verifies full GPU-layer offload and inspects measured overlapping execution slots in backend logs.',
            '- Hardware: the existing H100 MIG/vGPU allocation. Memory is sampled approximately once per second; backend logs record full transformer-layer offload and host buffers. Monitoring checks the shared Ollama service for competing activity.',
            '- Original abstracts are hash-checked after each complete model. Saved summaries and shared Ollama service settings remain unchanged.',
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
            'Qwen3.5-9B uses direct llama.cpp with the same Q4_K_M checkpoint after the Ollama 0.34.4 scheduler forced `qwen35` to one slot. '
            'The driver applies the pinned official HF template/tokenizer and checks representative token-ID parity, full GPU-layer offload and per-slot context each round. '
            'The original scheduler and binary remain unchanged. Startup diagnostics and the eight-request smoke test are preserved outside measured aggregates.','',
            'Gemma-4-12B uses direct llama.cpp text-only inference after Ollama stalled during empty-input initialization. '
            'The configuration skips that startup warmup, retains synthetic real-request warmup, and uses the embedded GGUF template/tokenizer with thinking off. '
            'Each round checks all 200 prompts for preserved system/user text and context budget. '
            '[Compatibility evidence](compatibility_notes_en.md) records both backend adjustments.','',
            '## Interpretation','',
            'The measurements compare complete inference configurations. Cross-model rates reflect architecture, Q4_K_M weights, frontend and template differences; '
            'within-model concurrency comparisons use the same workload and configuration. The Gemma run uses Q4_K_M weights, whereas the historical full-paper summary evaluation used HF bitsandbytes NF4.','',
            'Agreement and correlation measure score stability relative to each model\'s 2-request outputs. Independent relevance labels are needed to assess correctness and ranking quality. '
            'Each paper/profile/concurrency cell has one measured pass. Profile orders balance configuration position; repeated runs at the same setting are needed to estimate timing and score variability.','',
            'This saturated closed-loop workload uses a historical abstract collection and synthetic profiles. Transfer to a live feed depends on its input lengths, profile mix and arrival pattern. '
            'Full-paper summarization requires its own long-context, long-output benchmark. Output-token rates use each model\'s tokenizer.','',
            'GPU compute-utilization telemetry is unavailable, so resource reporting covers sampled memory and layer placement. Shared-service monitoring covers Ollama activity; other GPU work may affect timing. '
            'Gemma\'s embedded tokenizer was checked for input integrity and context budget; independent official-HF token-ID parity remains unverified. '
            'Its successful startup adjustment changes the frontend and warmup configuration together, leaving the original stall\'s kernel cause unresolved.','',
            '## Reproducibility and next steps','',
            f'Dataset SHA-256: `{dataset_hash}`.','',
            'Per-model `analysis.json` contains verified per-profile and combined measurements, engine evidence and the complete score-variation list. '
            'Each round retains its model-residency snapshot, server log, warmup responses, timed JSONL responses, GPU samples and status. '
            'Source checkpoints, alias settings, inherited model metadata and exact script hashes are preserved.','',
            'Next, assess relevance on a preselected independently reviewed sample, examine concurrency-dependent score changes, and compare rankings with the existing semantic baseline on matched inputs. '
            'Then test multiple abstracts per prompt at fixed GPU concurrency, using stable article IDs and cross-batch anchors. '
            'Together, these checks will support a configuration choice based on relevance quality, throughput and latency.','',
            'Server experiment root: `/data/SFT_demo/Oct/results/feed_matrix_20261031/`.']
    (root/'report_en.md').write_text('\n'.join(lines)+'\n')
    print('Wrote English report; full three-model coverage:',full)


if __name__=='__main__':main()
