#!/usr/bin/env python3
"""Gemma text-only matrix using the embedded GGUF template and tokenizer."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess

parent=Path(__file__).parent
path=parent/'benchmark_feed_matrix_llamacpp_20261031.py'
if not path.exists():path=parent/'benchmark_feed_matrix_llamacpp.py'
spec=importlib.util.spec_from_file_location('direct',path)
direct=importlib.util.module_from_spec(spec);spec.loader.exec_module(direct)
base=direct.base


def messages(text):
    return [{'role':'system','content':base.SYSTEM},{'role':'user','content':text}]


def generate(text):
    raw=direct.native('v1/chat/completions',{
        'model':'gemma4','stream':False,'messages':messages(text),
        'max_tokens':96,'temperature':0,'seed':42,'top_k':20,'top_p':.95,'min_p':0,
        'repeat_penalty':1,'presence_penalty':0,'chat_template_kwargs':{'enable_thinking':False},
        'response_format':{'type':'json_schema','json_schema':{'name':'relevance','strict':True,'schema':base.SCHEMA}}})
    choice=raw['choices'][0];usage=raw['usage']
    return {'message':{'content':choice['message']['content']},'done':choice['finish_reason']=='stop',
            'done_reason':choice['finish_reason'],'prompt_eval_count':usage['prompt_tokens'],
            'eval_count':usage['completion_tokens'],'prompt_eval_duration':None,'eval_duration':None,
            'native_llamacpp_response':raw,'input_token_count_method':'embedded GGUF tokenizer, chat API usage'}


def verify_rendering(out,items):
    checks=[]
    for item in items:
        rendered=direct.native('apply-template',{'messages':messages(item['prompt']),
            'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}})['prompt']
        count=len(direct.native('tokenize',{'content':rendered,'add_special':False,'parse_special':True})['tokens'])
        check={'paper_id':item['paper_id'],'prompt_preserved':item['prompt'] in rendered,
               'system_preserved':base.SYSTEM in rendered,'tokens':count,
               'within_context':0<count+base.OPTIONS['num_predict']+128<base.OPTIONS['num_ctx']}
        if not all(check[k] for k in ['prompt_preserved','system_preserved','within_context']):
            raise RuntimeError('Gemma embedded-template input integrity/budget check failed')
        checks.append(check)
    base.save(out/'renderer_check.json',{'method':'embedded GGUF template/tokenizer; no independent HF parity claim',
                                        'independent_hf_parity':False,'checked':len(checks),'checks':checks})


def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--model',required=True)
    parser.add_argument('--label',required=True);parser.add_argument('--smoke-only',action='store_true')
    args,_=parser.parse_known_args();os.umask(0o002)
    shown=base.api(11434,'show',{'model':args.model})
    direct.MODEL_PATH=Path(shlex.split(next(x for x in shown['modelfile'].splitlines() if x.startswith('FROM ')))[1])
    if direct.MODEL_PATH.parent!=Path('/data/SFT_demo/.models/ollama/blobs'):raise ValueError('Unexpected model store')
    model_hash=file_hash(direct.MODEL_PATH)
    if direct.MODEL_PATH.name!='sha256-'+model_hash:raise ValueError('Model checksum mismatch')
    direct.TEMPLATE_ARGS=['--no-warmup','--jinja','--reasoning','off','--reasoning-budget','0']
    direct.generate=generate;direct.verify_tokenization=verify_rendering
    out=args.root/args.label;out.mkdir(exist_ok=True)
    provenance={'backend':'llama_cpp','binary':direct.BINARY,'binary_sha256':file_hash(Path(direct.BINARY)),
        'binary_version':subprocess.check_output([direct.BINARY,'--version'],stderr=subprocess.STDOUT,text=True),
        'model_path':str(direct.MODEL_PATH),'model_sha256':model_hash,'thinking':False,'text_only':True,
        'driver_sha256':file_hash(Path(__file__)),'round_helper_sha256':file_hash(path),
        'cuda_backend':direct.cuda_environment()['GGML_BACKEND_PATH'],'template_arguments':direct.TEMPLATE_ARGS,
        'renderer':'embedded GGUF chat template and tokenizer; no independent HF parity check',
        'note':'Empty engine warmup disabled; synthetic real-request warmup remains excluded from timing.'}
    prior_path=out/'backend_provenance.json'
    if prior_path.exists() and json.loads(prior_path.read_text())!=provenance:
        raise ValueError('Frozen Gemma backend configuration changed')
    base.save(prior_path,provenance)
    if args.smoke_only:
        attempt=out/f'smoke_attempt{len(list(out.glob("smoke_attempt*")))+1:02d}';attempt.mkdir()
        items=json.loads((args.root/'dataset.json').read_text())['inputs'][:8]
        print(json.dumps(direct.run_round(attempt,args.model,base.PROFILES[0],2,items,direct.BINARY)),flush=True)
        return
    base.BINARY=direct.BINARY;base.run_round=direct.run_round;base.main()


if __name__=='__main__':main()
