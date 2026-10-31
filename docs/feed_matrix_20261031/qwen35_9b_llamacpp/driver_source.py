#!/usr/bin/env python3
"""Text-only llama.cpp path for the Qwen3.5 model blocked by Ollama's scheduler."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
from urllib.request import Request,urlopen

parent=Path(__file__).parent
base_path=parent/'benchmark_feed_matrix_20261031.py'
if not base_path.exists():base_path=parent/'benchmark_feed_matrix.py'
spec=importlib.util.spec_from_file_location('feed_base',base_path)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
BINARY='/data/SFT_demo/.tools/ollama/lib/ollama/llama-server'
PORT=11437
TOKENIZER=None
MODEL_PATH=None


def cuda_environment():
    env=os.environ.copy()
    env['LD_LIBRARY_PATH']='/data/SFT_demo/.tools/ollama/lib/ollama:/data/SFT_demo/.tools/ollama/lib/ollama/cuda_v13'
    env['GGML_BACKEND_PATH']='/data/SFT_demo/.tools/ollama/lib/ollama/cuda_v13/libggml-cuda.so'
    return env


def context_per_sequence(log_text):
    values=re.findall(r'n_ctx_(?:per_seq|seq)\s*=\s*(\d+)',log_text)
    return int(values[-1]) if values else None


def native(route,data=None):
    req=Request(f'http://127.0.0.1:{PORT}/{route}',data=json.dumps(data).encode() if data is not None else None,
                headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=180) as f:return json.load(f)


def formatted(text):
    return TOKENIZER.apply_chat_template([{'role':'system','content':base.SYSTEM},{'role':'user','content':text}],
                                         tokenize=False,add_generation_prompt=True,enable_thinking=False)


def generate(text):
    rendered=formatted(text)
    tokens=TOKENIZER.encode(rendered,add_special_tokens=False)
    if len(tokens)+base.OPTIONS['num_predict']+128>=base.OPTIONS['num_ctx']:
        raise ValueError('Rendered prompt does not fit the frozen context')
    raw=native('completion',{'prompt':rendered,'n_predict':96,'stream':False,'temperature':0,'seed':42,
                            'top_k':20,'top_p':.95,'min_p':0,'presence_penalty':0,'repeat_penalty':1,
                            'json_schema':base.SCHEMA,'cache_prompt':True})
    timing=raw.get('timings',{})
    limited=raw.get('stopped_limit',False) or raw.get('stop_type')=='limit'
    return {'message':{'content':raw.get('content','')},'done':bool(raw.get('stop',True)) and not raw.get('error'),
            'done_reason':'length' if limited else 'stop','prompt_eval_count':len(tokens),
            'prompt_eval_duration':int(timing.get('prompt_ms',0)*1e6),
            'eval_count':timing.get('predicted_n',raw.get('tokens_predicted',0)),
            'eval_duration':int(timing.get('predicted_ms',0)*1e6),
            'native_llamacpp_response':raw,'input_token_count_method':'pinned official HF tokenizer, verified against server tokenize'}


def run_round(out,model,profile,parallel,items,binary):
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',PORT))==0:raise RuntimeError('Private port occupied')
    command=[binary,'--model',str(MODEL_PATH),'--port',str(PORT),'--host','127.0.0.1',
             '--no-webui','--offline','-c',str(4096*parallel),'-np',str(parallel),'-ngl','999',
             '--flash-attn','auto','-b','1024','-ub','512','--no-context-shift',
             '--log-verbosity','4','--no-log-prefix','--no-log-timestamps','--no-jinja','--chat-template','chatml']
    base.save(out/'command.json',command)
    log_path=out/'server.log';log=log_path.open('w')
    env=cuda_environment()
    proc=subprocess.Popen(command,stdout=log,stderr=log,env=env,start_new_session=True)
    stop,busy=threading.Event(),threading.Event();samples=[];errors=[];worker=None;rows=[];phase='startup'
    try:
        for _ in range(240):
            if proc.poll() is not None:raise RuntimeError('Direct llama.cpp server exited')
            try:native('health');break
            except Exception:time.sleep(.5)
        else:raise RuntimeError('Direct model load timeout')
        text=log_path.read_text(errors='replace')
        layers=re.findall(r'offloaded\s+(\d+)/(\d+)\s+layers',text)
        if not layers or layers[-1][0]!=layers[-1][1]:raise RuntimeError('Model layers are not all GPU-offloaded')
        configured=base.slot_count(log_path)
        if configured!=parallel or context_per_sequence(text)!=4096:
            raise RuntimeError('Direct engine did not retain requested slots/context')
        # Confirm the official tokenizer agrees with the actual GGUF tokenizer, including role tokens.
        example=formatted(items[0]['prompt'])
        server_tokens=native('tokenize',{'content':example,'add_special':False,'parse_special':True})['tokens']
        official=TOKENIZER.encode(example,add_special_tokens=False)
        if server_tokens!=official:raise RuntimeError('Official and GGUF token IDs differ')
        base.save(out/'tokenizer_parity.json',{'tokens':len(official),'exact_token_ids_match':True})
        phase='warmup'
        def warm(i):
            pid=f'warmup{i:02d}'
            text=('This synthetic prospective study investigated cardiovascular and neurological biomarkers in adults, '
                  'including inflammatory pathways and treatment response. Participants received follow-up assessments. '
                  'The study reports associations and discusses uncertainty and limited generalizability. ')*(2+i%4)
            response=generate(base.prompt(profile,pid,text));base.validate(response,{'paper_id':pid,'profile_id':profile['profile_id']})
            return {'index':i,'response':response}
        with ThreadPoolExecutor(max_workers=parallel) as pool:warmed=list(pool.map(warm,range(2*parallel)))
        base.save(out/'warmup.json',warmed)
        # Residency is certified from the full-layer offload log, not inferred from a fabricated byte ratio.
        base.save(out/'loaded.json',{'backend':'llama_cpp','gpu_residency_verified':True,
                                    'offloaded_layers':int(layers[-1][0]),'total_layers':int(layers[-1][1]),
                                    'n_ctx_per_seq':4096,'effective_sequences':configured,'models':[]})
        def monitor():
            while not stop.is_set():
                try:
                    r=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu',
                                      '--format=csv,noheader,nounits'],text=True,capture_output=True,timeout=8,check=True)
                    samples.append({'utc':base.now(),'raw':r.stdout.strip()})
                    if base.api(11434,'ps').get('models'):busy.set()
                except Exception as error:errors.append(str(error))
                stop.wait(1)
        worker=threading.Thread(target=monitor,daemon=True);worker.start();phase='measurement'
        def infer(item):
            start=time.perf_counter();stamp=base.now()
            try:
                if busy.is_set():raise RuntimeError('Shared Ollama active')
                response=generate(item['prompt']);latency=time.perf_counter()-start
                answer=base.validate(response,item)
                return {**answer,'valid':True,'latency_s':latency,'request_started_utc':stamp,'finished_utc':base.now(),
                        'prompt_sha256':item['prompt_sha256'],'abstract_sha256':item['abstract_sha256'],'response':response}
            except Exception as error:
                return {'paper_id':item['paper_id'],'profile_id':item['profile_id'],'valid':False,'error':str(error),
                        'latency_s':time.perf_counter()-start,'request_started_utc':stamp,'finished_utc':base.now()}
        start=time.perf_counter()
        with (out/'responses.jsonl').open('a') as ledger:
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                for future in as_completed([pool.submit(infer,item) for item in items]):
                    row=future.result();rows.append(row);ledger.write(json.dumps(row)+'\n');ledger.flush()
                    if len(rows)%25==0:
                        base.save(out/'progress.json',{'completed':len(rows),'expected':len(items),'utc':base.now()})
                        print(json.dumps({'profile':profile['profile_id'],'parallel':parallel,'completed':len(rows)}),flush=True)
        elapsed=time.perf_counter()-start
        result={'state':'completed' if all(x['valid'] for x in rows) and not busy.is_set() else 'failed',
                'profile_id':profile['profile_id'],'parallel':parallel,'effective_sequences':configured,
                'requests':len(rows),'valid':sum(x['valid'] for x in rows),'elapsed_s':elapsed,
                'documents_per_minute':len(rows)*60/elapsed,'median_latency_s':statistics.median(x['latency_s'] for x in rows),
                'shared_service_activity':busy.is_set(),'finished_utc':base.now(),'backend':'llama_cpp'}
        base.save(out/'result.json',result)
        if result['state']!='completed':raise RuntimeError('Direct round has invalid responses or conflicting work')
        return result
    except Exception as error:
        base.save(out/'failure.json',{'phase':phase,'error':str(error),'saved_rows':len(rows),'utc':base.now()});raise
    finally:
        stop.set()
        if worker:worker.join(timeout=15)
        base.save(out/'gpu.json',{'samples':samples,'errors':errors})
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        log.close()


def main():
    global TOKENIZER,MODEL_PATH
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--model',required=True);parser.add_argument('--label',required=True);parser.add_argument('--smoke-only',action='store_true')
    args,_=parser.parse_known_args();os.umask(0o002)
    from huggingface_hub import HfApi,snapshot_download
    from transformers import AutoTokenizer
    metadata=HfApi().model_info('Qwen/Qwen3.5-9B')
    cache='/data/SFT_demo/.cache/huggingface/hub'
    path=snapshot_download('Qwen/Qwen3.5-9B',revision=metadata.sha,cache_dir=cache,
                          allow_patterns=['tokenizer*','chat_template.jinja','vocab.json','merges.txt','config.json','special_tokens_map.json'])
    TOKENIZER=AutoTokenizer.from_pretrained(path,local_files_only=True)
    shown=base.api(11434,'show',{'model':args.model})
    from_lines=[x for x in shown['modelfile'].splitlines() if x.startswith('FROM ')]
    MODEL_PATH=Path(shlex.split(from_lines[0])[1])
    if MODEL_PATH.parent!=Path('/data/SFT_demo/.models/ollama/blobs'):raise ValueError('Unexpected model source path')
    model_hash=hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    if MODEL_PATH.name!='sha256-'+model_hash:raise ValueError('Model blob hash mismatch')
    out=args.root/args.label;out.mkdir(exist_ok=True)
    provenance={'backend':'llama_cpp','binary':BINARY,'binary_sha256':hashlib.sha256(Path(BINARY).read_bytes()).hexdigest(),
                'binary_version':subprocess.check_output([BINARY,'--version'],stderr=subprocess.STDOUT,text=True),
                'model_path':str(MODEL_PATH),'model_sha256':model_hash,'tokenizer_revision':metadata.sha,
                'tokenizer_snapshot':path,'thinking':False,'text_only':True,
                'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'cuda_backend':cuda_environment()['GGML_BACKEND_PATH'],
                'note':'Separate backend; original Ollama scheduler restriction remains unchanged.'}
    if (out/'backend_provenance.json').exists() and not args.smoke_only:
        prior=json.loads((out/'backend_provenance.json').read_text())
        for key in ['binary_sha256','model_sha256','tokenizer_revision','driver_sha256','cuda_backend']:
            if prior.get(key)!=provenance[key]:raise ValueError('Frozen direct-backend configuration changed: '+key)
    base.save(out/'backend_provenance.json',provenance)
    if args.smoke_only:
        attempt=out/f'smoke_attempt{len(list(out.glob("smoke_attempt*")))+1:02d}';attempt.mkdir(exist_ok=False)
        inputs=json.loads((args.root/'dataset.json').read_text())['inputs'][:8]
        result=run_round(attempt,args.model,base.PROFILES[0],2,inputs,BINARY)
        print(json.dumps(result),flush=True);return
    base.BINARY=BINARY;base.run_round=run_round;base.main()


if __name__=='__main__':main()
