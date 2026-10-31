#!/usr/bin/env python3
"""Finish the approved matrix after the verified direct-Qwen3.5 compatibility probe."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

SCRIPTS=Path('/data/SFT_demo/Oct/scripts')
spec=importlib.util.spec_from_file_location('stages',SCRIPTS/'continue_feed_matrix_models_20261031.py')
stages=importlib.util.module_from_spec(spec);spec.loader.exec_module(stages)


def run(driver,label,model):
    status=stages.ROOT/label/'status.json'
    if status.exists() and json.loads(status.read_text())['state']=='completed':
        stages.verify(label);return
    stages.state('benchmarking_model',label=label,model=model,driver=driver)
    with (stages.ROOT/f'{label}_run.log').open('a') as log:
        r=subprocess.run([stages.PYTHON,'-u',str(SCRIPTS/driver),'--root',str(stages.ROOT),
                          '--model',model,'--label',label],stdout=log,stderr=log)
    if r.returncode:raise RuntimeError(f'{label} stopped; inspect its status and failed-attempt records')
    stages.verify(label)


def main():
    os.umask(0o002)
    try:
        stages.verify('qwen3_8b')
        probe=stages.ROOT/'qwen35_9b_direct_probe/smoke_attempt03'
        result=json.loads((probe/'result.json').read_text())
        assert result['state']=='completed' and result['valid']==result['requests']==8 and result['effective_sequences']==2
        assert json.loads((probe/'tokenizer_parity.json').read_text())['exact_token_ids_match']
        residency=json.loads((probe/'loaded.json').read_text())
        assert residency['offloaded_layers']==residency['total_layers']==33 and residency['n_ctx_per_seq']==4096
        shutil.copy2(stages.ROOT/'qwen35_9b_model_setup.json',stages.ROOT/'qwen35_9b_llamacpp_model_setup.json')
        run('benchmark_feed_matrix_llamacpp_20261031.py','qwen35_9b_llamacpp','study-qwen35-9b-q4:20261031')
        stages.prepare_model('gemma4:12b-it-q4_K_M','study-gemma4-12b-q4:20261031','gemma4_12b')
        run('benchmark_feed_matrix_20261031.py','gemma4_12b','study-gemma4-12b-q4:20261031')
        stages.state('all_models_verified',labels=['qwen3_8b','qwen35_9b_llamacpp','gemma4_12b'],timed_inferences=5400)
    except Exception as error:
        stages.state('blocked',error=str(error));raise


if __name__=='__main__':main()
