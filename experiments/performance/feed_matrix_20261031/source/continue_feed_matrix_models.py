#!/usr/bin/env python3
"""Continue approved model stages only after complete independent baseline checks."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from urllib.request import Request,urlopen

ROOT=Path('/data/SFT_demo/Oct/results/feed_matrix_20261031')
SCRIPTS=Path('/data/SFT_demo/Oct/scripts')
PYTHON='/data/SFT_demo/.venv/bin/python'
BINARY='/data/SFT_demo/.tools/ollama/bin/ollama'
STATE=ROOT/'pipeline_status.json'


def now():return datetime.now(timezone.utc).isoformat()
def save(path,obj):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(obj,indent=2)+'\n');temp.chmod(0o664);temp.replace(path)
def state(phase,**data):
    save(STATE,{'phase':phase,'updated_utc':now(),**data});print(json.dumps({'phase':phase,**data}),flush=True)
def api(port,route,payload=None):
    req=Request(f'http://127.0.0.1:{port}/api/{route}',data=json.dumps(payload).encode() if payload is not None else None,
                headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=3600) as f:return json.load(f)


def verify(label):
    result=subprocess.run([PYTHON,str(SCRIPTS/'analyze_feed_matrix_20261031.py'),'--root',str(ROOT),'--label',label],
                          text=True,capture_output=True)
    (ROOT/label/'verification.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(f'{label} verification failed: {result.stderr[-1000:]}')
    analysis=json.loads((ROOT/label/'analysis.json').read_text())
    if analysis['state']!='verified_complete' or analysis['timed_requests']!=1800:
        raise RuntimeError('Baseline incomplete; do not advance')
    state('model_verified',label=label,aggregates=analysis['aggregates'])


def prepare_model(source,alias,label):
    port=11438
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Pull-service port already occupied')
    if api(11434,'ps').get('models'):raise RuntimeError('Shared Ollama active')
    env=os.environ.copy();env.update(OLLAMA_HOST=f'127.0.0.1:{port}',OLLAMA_MODELS='/data/SFT_demo/.models/ollama')
    log=(ROOT/f'{label}_model_setup.log').open('a')
    proc=subprocess.Popen([BINARY,'serve'],env=env,stdout=log,stderr=log,start_new_session=True)
    try:
        for _ in range(100):
            if proc.poll() is not None:raise RuntimeError('Model setup service exited')
            try:api(port,'version');break
            except Exception:time.sleep(.25)
        else:raise RuntimeError('Model setup startup timeout')
        tags=api(port,'tags')['models']
        if source not in {x['name'] for x in tags}:
            state('downloading_model',label=label,source=source)
            req=Request(f'http://127.0.0.1:{port}/api/pull',data=json.dumps({'model':source,'stream':True}).encode(),
                        headers={'Content-Type':'application/json'})
            last=None
            with urlopen(req,timeout=3600) as f:
                for line in f:
                    event=json.loads(line)
                    if 'error' in event:raise RuntimeError(event['error'])
                    total=event.get('total',0);percent=int(event.get('completed',0)*100/total) if total else None
                    marker=(event.get('status'),percent//5 if percent is not None else None)
                    if marker!=last:
                        state('downloading_model',label=label,source=source,progress=event);last=marker
        source_tag=next(x for x in api(port,'tags')['models'] if x['name']==source)
        if source_tag['details']['quantization_level']!='Q4_K_M':
            raise RuntimeError('Expected explicit Q4_K_M checkpoint')
        # Match the old Qwen effective penalties; source-specific templates/stops remain intact.
        parameters={'presence_penalty':0,'repeat_penalty':1,'top_k':20,'top_p':.95,'min_p':0}
        existing={x['name']:x for x in api(port,'tags')['models']}
        setup_path=ROOT/f'{label}_model_setup.json'
        if alias not in existing:
            state('creating_pinned_alias',label=label,source=source,alias=alias)
            api(port,'create',{'model':alias,'from':source,'parameters':parameters,'stream':False})
        shown=api(port,'show',{'model':alias})
        target=next(x for x in api(port,'tags')['models'] if x['name']==alias)
        setup={'source':source_tag,'alias':target,'parameter_overrides':parameters,'show':shown,
               'runtime':api(port,'version'),'created_or_checked_utc':now()}
        if setup_path.exists():
            prior=json.loads(setup_path.read_text())
            if prior['source']['digest']!=source_tag['digest'] or prior['alias']['digest']!=target['digest']:
                raise RuntimeError('Previously frozen model digest changed')
        else:save(setup_path,setup)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        log.close()


def main():
    os.umask(0o002)
    try:
        state('waiting_for_qwen3_8b')
        while True:
            status_path=ROOT/'qwen3_8b/status.json'
            if status_path.exists():
                status=json.loads(status_path.read_text())
                if status['state']=='completed':break
                if status['state'] in ['blocked','failed']:raise RuntimeError('Qwen3-8B stopped: '+str(status))
            time.sleep(15)
        verify('qwen3_8b')
        for source,alias,label in [('qwen3.5:9b-q4_K_M','study-qwen35-9b-q4:20261031','qwen35_9b'),
                                   ('gemma4:12b-it-q4_K_M','study-gemma4-12b-q4:20261031','gemma4_12b')]:
            if (ROOT/label/'status.json').exists() and json.loads((ROOT/label/'status.json').read_text())['state']=='completed':
                verify(label);continue
            prepare_model(source,alias,label)
            state('benchmarking_model',label=label,model=alias)
            with (ROOT/f'{label}_run.log').open('a') as log:
                r=subprocess.run([PYTHON,'-u',str(SCRIPTS/'benchmark_feed_matrix_20261031.py'),
                                  '--root',str(ROOT),'--model',alias,'--label',label],stdout=log,stderr=log)
            if r.returncode:raise RuntimeError(f'{label} benchmark stopped; inspect its status and failure records')
            verify(label)
        state('all_models_verified',labels=['qwen3_8b','qwen35_9b','gemma4_12b'],timed_inferences=5400)
    except Exception as error:
        state('blocked',error=str(error));raise


if __name__=='__main__':main()
