#!/usr/bin/env python3
"""Bounded text-only Gemma probe without the stalled empty-input engine warmup."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time
from urllib.request import Request,urlopen

SCRIPTS=Path('/data/SFT_demo/Oct/scripts')
spec=importlib.util.spec_from_file_location('direct',SCRIPTS/'benchmark_feed_matrix_llamacpp_20261031.py')
direct=importlib.util.module_from_spec(spec);spec.loader.exec_module(direct)
base=direct.base
ROOT=Path('/data/SFT_demo/Oct/results/feed_matrix_20261031')
PORT=11437


def api(route,data=None):
    request=Request(f'http://127.0.0.1:{PORT}/{route}',data=json.dumps(data).encode() if data is not None else None,
                    headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=75) as f:return json.load(f)


def main():
    os.umask(0o002)
    root=ROOT/'gemma4_direct_probe';root.mkdir(exist_ok=True)
    out=root/f'attempt{len(list(root.glob("attempt*")))+1:02d}';out.mkdir()
    setup=json.loads((ROOT/'gemma4_12b_model_setup.json').read_text())
    model=Path(shlex.split(next(x for x in setup['show']['modelfile'].splitlines() if x.startswith('FROM ')))[1])
    command=[direct.BINARY,'--model',str(model),'--port',str(PORT),'--host','127.0.0.1','--offline','--no-webui',
             '-c','8192','-np','2','-ngl','999','--flash-attn','auto','-b','1024','-ub','512',
             '--no-warmup','--jinja','--reasoning','off','--reasoning-budget','0',
             '--log-verbosity','4','--no-log-prefix','--no-log-timestamps']
    base.save(out/'command.json',command)
    log=(out/'server.log').open('w');proc=subprocess.Popen(command,env=direct.cuda_environment(),stdout=log,stderr=log,start_new_session=True)
    phase='startup'
    try:
        for _ in range(180):
            if proc.poll() is not None:raise RuntimeError('Gemma native server exited')
            try:api('health');break
            except Exception:time.sleep(.5)
        else:raise RuntimeError('Native initialization timed out')
        text=(out/'server.log').read_text(errors='replace')
        layers=re.findall(r'offloaded\s+(\d+)/(\d+)\s+layers',text)
        if not layers or layers[-1][0]!=layers[-1][1]:raise RuntimeError('Not all Gemma layers offloaded')
        if base.slot_count(out/'server.log')!=2 or direct.context_per_sequence(text)!=4096:
            raise RuntimeError('Wrong Gemma slot/context configuration')
        phase='real_requests'
        items=json.loads((ROOT/'dataset.json').read_text())['inputs'][:8]
        def infer(item):
            response=api('v1/chat/completions',{'model':'gemma4','stream':False,'messages':[
                {'role':'system','content':base.SYSTEM},{'role':'user','content':item['prompt']}],
                'max_tokens':96,'temperature':0,'seed':42,'top_k':20,'top_p':.95,'min_p':0,'repeat_penalty':1,'presence_penalty':0,
                'chat_template_kwargs':{'enable_thinking':False},
                'response_format':{'type':'json_schema','json_schema':{'name':'relevance','strict':True,'schema':base.SCHEMA}}})
            base.save(out/f'{item["paper_id"]}.json',response)
            choice=response['choices'][0]
            normalized={'message':{'content':choice['message']['content']},'done':True,
                        'done_reason':'length' if choice['finish_reason']=='length' else 'stop',
                        'prompt_eval_count':response['usage']['prompt_tokens']}
            answer=base.validate(normalized,item)
            return {**answer,'finish_reason':choice['finish_reason'],'usage':response['usage']}
        with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(infer,items))
        base.save(out/'result.json',{'state':'completed','requests':8,'valid':len(rows),'rows':rows,
                                    'offloaded_layers':layers[-1],'effective_sequences':2,'context_per_sequence':4096,
                                    'backend':'llama_cpp','empty_input_warmup':False,'flash_attention':'auto'})
        print('Gemma probe passed: 8/8 valid real requests',flush=True)
    except Exception as error:
        base.save(out/'failure.json',{'phase':phase,'error':str(error),'utc':base.now()});raise
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        log.close()


if __name__=='__main__':main()
