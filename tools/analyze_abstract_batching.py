#!/usr/bin/env python3
"""Verify the two bounded batching pilots and generate an English report."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics


def percentile(values, q):
    values = sorted(values)
    x = (len(values)-1)*q
    lo = int(x)
    hi = min(lo+1, len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(x-lo)


def inspect_engine(path, warm_count):
    text = path.read_text(errors='replace')
    active, maximum, launched, released = set(), 0, 0, 0
    for line in text.splitlines():
        start = re.search(r'slot launch_slot_: id\s+(\d+).*processing task', line)
        end = re.search(r'slot\s+release: id\s+(\d+).*stop processing', line)
        if start:
            launched += 1
            if launched > warm_count:
                slot = int(start[1])
                assert slot not in active, 'A slot was launched without release'
                active.add(slot)
                maximum = max(maximum, len(active))
        elif end:
            released += 1
            active.discard(int(end[1]))
    assert not active and launched == released == 32+warm_count
    return {'configured_sequences': int(re.search(r'n_seq_max\s*=\s*(\d+)', text)[1]),
            'configured_token_batch': int(re.search(r'n_batch\s*=\s*(\d+)', text)[1]),
            'observed_peak_active_measured_slots': maximum,
            'measured_tasks': launched-warm_count}


def analyze(folder):
    read = lambda name: json.loads((folder/name).read_text())
    protocol, status, rounds, inputs = read('protocol.json'), read('status.json'), read('rounds.json'), read('inputs.json')
    assert status['state'] == 'completed' and status['inferences'] == 192
    assert [r['parallel'] for r in rounds] == [1,2,4,4,2,1]
    assert read('source_integrity.json') == {'checked':200,'changed':[]}
    expected = {x['paper_id'] for x in inputs}
    assert len(inputs) == len(expected) == 32
    baseline = {x['paper_id']: x['relevance'] for x in rounds[0]['results']}
    engine = []
    for r in rounds:
        assert len(r['results']) == r['valid'] == 32
        assert {x['paper_id'] for x in r['results']} == expected
        for row in r['results']:
            response = read(f'round{r["round"]}_{row["paper_id"]}.json')
            answer = json.loads(response['message']['content'])
            assert set(answer) == {'paper_id','relevance'} and answer['paper_id'] == row['paper_id']
            assert type(answer['relevance']) is int and 0 <= answer['relevance'] <= 3
            assert answer['relevance'] == row['relevance'] and row['valid']
            assert response['done'] and response['done_reason'] != 'length'
            assert hashlib.sha256(response['message']['content'].strip().encode()).hexdigest() == row['output_sha256']
            assert response['prompt_eval_count'] + protocol['options']['num_predict'] < protocol['options']['num_ctx']
        assert abs(r['papers_per_minute'] - 32*60/r['elapsed_s']) < 1e-9
        loaded = read(f'loaded_round{r["round"]}.json')['models']
        assert len(loaded) == 1 and loaded[0]['size_vram'] >= .95*loaded[0]['size']
        warm_count = 1 if protocol.get('warmup_policy', 'single_request') == 'single_request' else 2*r['parallel']
        evidence = inspect_engine(folder/f'server_round{r["round"]}.log', warm_count)
        assert evidence['configured_sequences'] == evidence['observed_peak_active_measured_slots'] == r['parallel']
        evidence.update(round=r['round'], parallel=r['parallel'])
        engine.append(evidence)
    groups=[]
    for parallel in [1,2,4]:
        subset=[r for r in rounds if r['parallel']==parallel]
        rows=[x for r in subset for x in r['results']]
        elapsed=sum(r['elapsed_s'] for r in subset)
        memory=[]
        errors=[]
        for r in subset:
            samples=read(f'gpu_round{r["round"]}.json')
            errors.extend(samples['errors'])
            for sample in samples['samples']:
                try: memory.append(float(sample['raw'].split(',')[0].strip()))
                except ValueError: pass
        groups.append({'parallel':parallel,'requests':len(rows),'valid':sum(x['valid'] for x in rows),
                       'elapsed_s':elapsed,'papers_per_minute':len(rows)*60/elapsed,
                       'output_tokens_per_second':sum(x['eval_count'] for x in rows)/elapsed,
                       'median_latency_s':statistics.median(x['latency_s'] for x in rows),
                       'p95_latency_s':percentile([x['latency_s'] for x in rows],.95),
                       'peak_sampled_memory_mib':max(memory) if memory else None,
                       'round_throughputs':[r['papers_per_minute'] for r in subset],
                       'score_disagreements_vs_first_serial_round':sum(x['relevance']!=baseline[x['paper_id']] for x in rows),
                       'telemetry_errors':errors})
    for g in groups:
        g['throughput_change_percent']=(g['papers_per_minute']/groups[0]['papers_per_minute']-1)*100
    return {'run':folder.name,'protocol':protocol,'groups':groups,'engine_evidence':engine,
            'score_vectors':[{x['paper_id']:x['relevance'] for x in r['results']} for r in rounds],
            'input_tokens_min':min(x['prompt_eval_count'] for r in rounds for x in r['results']),
            'input_tokens_max':max(x['prompt_eval_count'] for r in rounds for x in r['results']),
            'output_tokens_min':min(x['eval_count'] for r in rounds for x in r['results']),
            'output_tokens_max':max(x['eval_count'] for r in rounds for x in r['results']),
            'input_hashes':{x['paper_id']:x['prompt_sha256'] for x in inputs}}


def table(result):
    lines=['| Concurrent requests | Inferences | Valid | Documents/min | Change vs serial | Output tokens/s | Median latency (s) | p95 latency (s) | Peak sampled memory (MiB) |',
           '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for g in result['groups']:
        lines.append(f'| {g["parallel"]} | {g["requests"]} | {g["valid"]} | {g["papers_per_minute"]:.2f} | {g["throughput_change_percent"]:+.1f}% | {g["output_tokens_per_second"]:.2f} | {g["median_latency_s"]:.3f} | {g["p95_latency_s"]:.3f} | {g["peak_sampled_memory_mib"]:.0f} |')
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args()
    initial=analyze(args.root/'qwen_abstract_batching_20261031')
    warm=analyze(args.root/'qwen_abstract_batching_warm_20261031')
    assert initial['input_hashes']==warm['input_hashes']
    for key in ['model','system','profile','schema','options','sequence','tokenizer_sha256']:
        assert initial['protocol'][key]==warm['protocol'][key]
    result={'state':'verified','measured_inferences':384,'valid_inferences':384,'initial':initial,'representative_warmup':warm}
    (args.root/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    variations=[]
    for index, vector in enumerate(warm['score_vectors'], 1):
        for pid, score in vector.items():
            baseline=warm['score_vectors'][0][pid]
            if score != baseline:
                variations.append({'round':index,'parallel':warm['protocol']['sequence'][index-1],
                                   'paper_id':pid,'first_serial_score':baseline,'score':score})
    (args.root/'score_variation.json').write_text(json.dumps(variations,indent=2)+'\n')
    best=max(warm['groups'],key=lambda x:x['papers_per_minute'])
    disagreements=[(g['parallel'],g['score_disagreements_vs_first_serial_round']) for g in warm['groups']]
    report=f'''# Qwen3-8B Abstract Batching Pilot

Date: October 31, 2026.

## Result and scope

The private Ollama backend processed overlapping independent requests on the available H100 MIG allocation. Both six-round experiments completed: **384/384 measured requests** returned valid paper IDs and integer relevance scores with normal completion. No source abstracts changed. This is a short-output relevance-scoring throughput pilot, not full-paper summarization or a validated ranking-quality evaluation.

Under representative parallel warmup, the best observed configuration was **{best['parallel']} concurrent requests**, at **{best['papers_per_minute']:.2f} documents/minute**, a **{best['throughput_change_percent']:+.1f}%** change relative to its paired serial baseline. It is a candidate setting for a larger quality-controlled test, not a proven optimum.

## Representative parallel warmup: primary comparison

Each fresh private server was warmed with 2 × concurrency actual abstract requests submitted through the target number of workers (nominally two waves, with no barrier between them). Warmup articles were disjoint from the measured 32-paper set. Warmup requests are excluded from timing and the 384-inference total. All other workload and model settings match the initial pilot.

{table(warm)}

## Initial pilot: retained startup sensitivity check

The initial pilot warmed each server with one short request. Its four-way rounds differed substantially, and the first parallel requests had elevated latency. This motivated the second experiment; no initial observations were discarded or pooled into the primary table. Different warmup policies can alter startup state and prefix-cache behavior, so their difference is not proof of one isolated cause.

{table(initial)}

## Protocol

- Model: installed `qwen3:8b`, Q4_K_M; Ollama {warm['protocol']['ollama']['version']}; model digest `{warm['protocol']['model']['digest']}`. No model download or upgrade.
- Data: 32 abstracts sampled from the existing 200-paper collection, eight from each token-length quartile, with seed 42 and one fixed seeded ordering. Each concurrency receives the same 32 measured prompts twice, in sequence 1–2–4–4–2–1.
- Workload: one independent abstract per request, one oncology research-interest profile, relevance scale 0–3. The JSON output contains only paper ID and relevance. This tests request batching, not concatenating multiple abstracts into one context. It does not compare different user profiles or an existing semantic ranker.
- Context: 4,096 tokens; output cap: 96 tokens; temperature 0; seed 42; thinking disabled. Observed input counts in the primary comparison are {warm['input_tokens_min']}–{warm['input_tokens_max']} tokens and output counts {warm['output_tokens_min']}–{warm['output_tokens_max']} tokens. No input exceeded the reserved context budget.
- One model per private server, loopback port 11436, requested parallelism 1, 2 or 4. The existing shared service on port 11434 was read for inventory/activity and was not reconfigured. Each private server was terminated after its round. The existing model remained installed.
- Timings exclude reading, tokenization, server startup and warmup; they include request/response handling, queuing, generation, validation and raw response writes. Group throughput is total documents divided by summed round durations. Median and p95 use all 64 request latencies per setting; p95 is a linearly interpolated sample percentile. Prefix caching remains enabled.
- Memory is sampled approximately once per second. GPU compute utilization is unavailable on this allocation; memory occupancy is not compute utilization or evidence of saturation. Monitoring checks the shared Ollama model state; other processes or activity outside this check cannot be completely ruled out.

## Engine evidence and output checks

Private engine logs record `n_seq_max` of 1, 2 and 4 and overlapping active task slots reaching exactly those counts during measured requests. Every measured task has a matching release. The model was GPU-resident in all rounds. The engine also adjusts its configured token batch with parallelism; this is an end-to-end Ollama configuration comparison, not an isolated client-thread or fixed-kernel-batch experiment. This evidence goes beyond client HTTP overlap, but no CUDA kernel profiler was run.

All 384 raw responses were independently re-parsed; IDs, score type/range, completion, context budget and output hashes were checked. All 12 per-round throughputs and the grouped means were recalculated from raw rows. The 200 original abstract hashes were checked after each pilot. The scripts, prompt snapshots, engine logs, GPU samples and raw responses remain alongside these results.

Score disagreements versus the first serial round in the primary experiment (over 64 observations per setting) are: {disagreements}. These include repeated serial observations and are indicators of output repeatability only. A changed score may arise from batching, numerics, prompt caching or selection of a different valid response. There are no gold relevance labels, so neither agreement nor valid JSON certifies correctness. Both latency and quality must be checked before a production rollout.

## Next step

Recheck the most promising setting on a larger frozen feed and multiple profiles, with independently assessed relevance and the real semantic-ranking baseline. Preserve an explicit output-quality guard alongside throughput. Full-paper summarization needs a separate memory/context benchmark; these short-output numbers must not be extrapolated to it. Consider a separate compatible vLLM experiment only after this baseline and workload are fixed; this run does not compare inference engines.

Server results: `/data/SFT_demo/Oct/results/qwen_abstract_batching_20261031/` and `/data/SFT_demo/Oct/results/qwen_abstract_batching_warm_20261031/`.
'''
    (args.root/'report_en.md').write_text(report)
    print(json.dumps({'best':best,'score_disagreements':disagreements,'state':'verified'},indent=2))


if __name__=='__main__':
    main()
