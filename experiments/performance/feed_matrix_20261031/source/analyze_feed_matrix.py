#!/usr/bin/env python3
"""Audit feed-matrix ledgers and compare throughput and ordinal-score stability."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import statistics


def sha(raw):return hashlib.sha256(raw).hexdigest()


def percentile(values,q):
    values=sorted(values);position=(len(values)-1)*q;lo=math.floor(position);hi=math.ceil(position)
    return values[lo]+(values[hi]-values[lo])*(position-lo)


def average_ranks(values):
    ordered=sorted(range(len(values)),key=values.__getitem__);ranks=[0.0]*len(values);start=0
    while start<len(ordered):
        end=start+1
        while end<len(ordered) and values[ordered[end]]==values[ordered[start]]:end+=1
        rank=(start+1+end)/2
        for i in ordered[start:end]:ranks[i]=rank
        start=end
    return ranks


def spearman(a,b):
    x,y=average_ranks(a),average_ranks(b)
    mx,my=statistics.mean(x),statistics.mean(y)
    denom=math.sqrt(sum((v-mx)**2 for v in x)*sum((v-my)**2 for v in y))
    return sum((i-mx)*(j-my) for i,j in zip(x,y))/denom if denom else None


def engine_evidence(log_path,warmup_count):
    text=log_path.read_text(errors='replace');slots=set();peak=0;launched=0;measured=0
    for line in text.splitlines():
        start=re.search(r'slot launch_slot_: id\s+(\d+).*processing task',line)
        end=re.search(r'slot\s+release: id\s+(\d+).*stop processing',line)
        if start:
            launched+=1
            if launched>warmup_count:
                slots.add(int(start[1]));measured+=1;peak=max(peak,len(slots))
        if end:slots.discard(int(end[1]))
    configured=re.findall(r'n_seq_max\s*=\s*(\d+)',text)
    return {'configured_sequences':int(configured[-1]) if configured else None,'observed_measured_slot_peak':peak,
            'measured_task_launches':measured,'all_measured_slots_released':not slots}


def analyze(root,label):
    folder=root/label;dataset=json.loads((root/'dataset.json').read_text())
    protocol=json.loads((folder/'protocol.json').read_text());status=json.loads((folder/'status.json').read_text())
    assert protocol['dataset_sha256']==sha((root/'dataset.json').read_bytes())
    expected={(x['profile_id'],x['paper_id']):x for x in dataset['inputs']};assert len(expected)==600
    data={};rounds=[];variations=[]
    for profile in dataset['profiles']:
        pid=profile['profile_id'];data[pid]={}
        for parallel in [2,4,8]:
            accepted=folder/f'{pid}_p{parallel}'/'accepted.json'
            if not accepted.exists():continue
            r=json.loads(accepted.read_text());attempt=folder/r['attempt']
            assert r['state']=='completed' and r['requests']==r['valid']==200
            assert r['effective_sequences']==parallel
            records=[json.loads(x) for x in (attempt/'responses.jsonl').read_text().splitlines()]
            assert len(records)==200 and {x['paper_id'] for x in records}=={f'paper{i:03d}' for i in range(1,201)}
            for x in records:
                assert x['profile_id']==pid
                item=expected[(pid,x['paper_id'])];raw=x['response'];answer=json.loads(raw['message']['content'])
                assert answer=={k:x[k] for k in ['paper_id','profile_id','relevance']}
                assert set(answer)=={'paper_id','profile_id','relevance'}
                assert x['valid'] and type(x['relevance']) is int and 0<=x['relevance']<=3
                assert x['abstract_sha256']==item['abstract_sha256'] and x['prompt_sha256']==item['prompt_sha256']
                assert raw['done'] and raw['done_reason']!='length'
                native=raw.get('native_llamacpp_response')
                if native is not None:
                    if 'choices' in native:
                        assert native['choices'][0]['message']['content']==raw['message']['content']
                        assert native['choices'][0]['finish_reason']==raw['done_reason']=='stop'
                        assert native['usage']['prompt_tokens']==raw['prompt_eval_count']
                        assert native['usage']['completion_tokens']==raw['eval_count']
                    else:
                        assert native['content']==raw['message']['content']
                        assert native['timings']['predicted_n']==raw['eval_count']
                assert raw['prompt_eval_count']+protocol['options']['num_predict']+128<protocol['options']['num_ctx']
                assert math.isfinite(x['latency_s']) and x['latency_s']>0
            assert math.isclose(r['documents_per_minute'],len(records)*60/r['elapsed_s'],abs_tol=1e-9)
            observed_span=(max(datetime.fromisoformat(x['finished_utc']) for x in records)-
                           min(datetime.fromisoformat(x['request_started_utc']) for x in records)).total_seconds()
            assert observed_span>0 and abs(r['elapsed_s']-observed_span)<max(2.0,r['elapsed_s']*.02)
            residency=json.loads((attempt/'loaded.json').read_text())
            engine_text=(attempt/'server.log').read_text(errors='replace')
            offloaded=re.findall(r'offloaded\s+(\d+)/(\d+)\s+layers',engine_text)
            contexts=re.findall(r'n_ctx_(?:per_seq|seq)\s*=\s*(\d+)',engine_text)
            assert offloaded and offloaded[-1][0]==offloaded[-1][1] and int(offloaded[-1][0])>0
            assert contexts and int(contexts[-1])==4096
            if residency.get('backend')=='llama_cpp':
                assert residency['gpu_residency_verified'] and residency['offloaded_layers']==residency['total_layers']>0
                assert residency['n_ctx_per_seq']==4096 and residency['effective_sequences']==parallel
                parity=attempt/'tokenizer_parity.json'
                if parity.exists():
                    assert json.loads(parity.read_text())['exact_token_ids_match']
                else:
                    renderer=json.loads((attempt/'renderer_check.json').read_text())
                    assert renderer['independent_hf_parity'] is False
                    assert renderer['checked']==len(renderer['checks'])==200
                    assert {x['paper_id'] for x in renderer['checks']}=={x['paper_id'] for x in records}
                    assert all(x['prompt_preserved'] and x['system_preserved'] and x['within_context']
                               and x['tokens']>0 and x['tokens']+protocol['options']['num_predict']+128<4096 for x in renderer['checks'])
            else:
                loaded=residency['models']
                assert len(loaded)==1 and loaded[0]['size_vram']>=.95*loaded[0]['size']
                assert loaded[0]['digest']==protocol['model']['digest'],'Model tag resolved to different weights during the matrix'
            evidence=engine_evidence(attempt/'server.log',2*parallel)
            assert evidence['configured_sequences']==parallel and evidence['observed_measured_slot_peak']==parallel
            assert evidence['measured_task_launches']==200 and evidence['all_measured_slots_released']
            samples=json.loads((attempt/'gpu.json').read_text());memory=[]
            for x in samples['samples']:
                try:memory.append(float(x['raw'].split(',')[0].strip()))
                except ValueError:pass
            assert memory,'Missing memory telemetry'
            r.update(observed_request_span_s=observed_span,
                     p95_latency_s=percentile([x['latency_s'] for x in records],.95),
                     median_latency_s=statistics.median(x['latency_s'] for x in records),
                     peak_sampled_memory_mib=max(memory),
                     output_tokens_per_second=sum(x['response']['eval_count'] for x in records)/r['elapsed_s'],
                     input_tokens_min=min(x['response']['prompt_eval_count'] for x in records),
                     input_tokens_max=max(x['response']['prompt_eval_count'] for x in records),
                     engine=evidence,telemetry_errors=samples['errors'])
            rounds.append(r);data[pid][parallel]={x['paper_id']:x for x in records}
    complete=len(rounds)==9 and status['state']=='completed'
    groups=[]
    for p in [2,4,8]:
        subset=[r for r in rounds if r['parallel']==p]
        if not subset:continue
        records=[x for pid in data if p in data[pid] for x in data[pid][p].values()]
        elapsed=sum(x['elapsed_s'] for x in subset)
        groups.append({'parallel':p,'profiles':len(subset),'requests':len(records),'elapsed_s':elapsed,
                       'documents_per_minute':len(records)*60/elapsed,
                       'median_latency_s':statistics.median(x['latency_s'] for x in records),
                       'p95_latency_s':percentile([x['latency_s'] for x in records],.95),
                       'peak_sampled_memory_mib':max(x['peak_sampled_memory_mib'] for x in subset),
                       'output_tokens_per_second':sum(x['response']['eval_count'] for x in records)/elapsed})
    distributions=[{'profile_id':pid,'parallel':p,
                    'counts':{str(score):sum(x['relevance']==score for x in records.values()) for score in range(4)}}
                   for pid,groups_by_p in data.items() for p,records in groups_by_p.items()]
    stability=[]
    for pid,by_parallel in data.items():
        if 2 not in by_parallel:continue
        base=by_parallel[2]
        for p in [4,8]:
            if p not in by_parallel:continue
            other=by_parallel[p];ids=sorted(base)
            a=[base[i]['relevance'] for i in ids];b=[other[i]['relevance'] for i in ids]
            stability.append({'profile_id':pid,'parallel':p,'reference_parallel':2,'pairs':200,
                              'exact_agreement':sum(i==j for i,j in zip(a,b))/200,
                              'mean_absolute_difference':statistics.mean(abs(i-j) for i,j in zip(a,b)),
                              'relevant_threshold_flips':sum((i>=2)!=(j>=2) for i,j in zip(a,b)),
                              'tied_rank_spearman':spearman(a,b)})
            for i in ids:
                if base[i]['relevance']!=other[i]['relevance']:
                    variations.append({'profile_id':pid,'paper_id':i,'parallel':p,'p2':base[i]['relevance'],'score':other[i]['relevance']})
    if complete:
        assert json.loads((folder/'source_integrity.json').read_text())=={'checked':200,'changed':[]}
    backend_path=folder/'backend_provenance.json'
    if backend_path.exists():
        provenance=json.loads(backend_path.read_text())
        assert provenance['binary_sha256']==protocol['binary_sha256']
        assert Path(provenance['model_path']).name=='sha256-'+provenance['model_sha256']
    result={'label':label,'model':protocol['model'],'state':'verified_complete' if complete else 'verified_partial',
            'backend':json.loads(backend_path.read_text()) if backend_path.exists() else {'backend':'ollama','version':protocol['ollama_version']},
            'timed_requests':sum(x['requests'] for x in rounds),'rounds':rounds,'aggregates':groups,
            'stability_vs_p2':stability,'score_variations':variations,'score_distributions':distributions,
            'dataset_sha256':protocol['dataset_sha256'],'no_relevance_gold_labels':True}
    (folder/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path);p.add_argument('--label',required=True)
    args=p.parse_args();r=analyze(args.root,args.label)
    print(json.dumps({k:r[k] for k in ['label','state','timed_requests','aggregates','stability_vs_p2']},indent=2))


if __name__=='__main__':main()
