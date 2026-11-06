#!/usr/bin/env python3
"""Complete Gemma after both Qwen matrices and the native Gemma smoke test pass."""
import importlib.util
import json
import os
from pathlib import Path
import shutil

SCRIPTS=Path('/data/SFT_demo/Oct/scripts')
spec=importlib.util.spec_from_file_location('continuation',SCRIPTS/'continue_feed_matrix_native_20261031.py')
continuation=importlib.util.module_from_spec(spec);spec.loader.exec_module(continuation)
stages=continuation.stages


def main():
    os.umask(0o002)
    try:
        stages.verify('qwen3_8b');stages.verify('qwen35_9b_llamacpp')
        probe=stages.ROOT/'gemma4_native_adapter_probe/smoke_attempt01'
        result=json.loads((probe/'result.json').read_text())
        assert result['state']=='completed' and result['requests']==result['valid']==8
        assert result['effective_sequences']==2
        assert json.loads((probe/'renderer_check.json').read_text())['checked']==8
        shutil.copy2(stages.ROOT/'gemma4_12b_model_setup.json',stages.ROOT/'gemma4_12b_llamacpp_model_setup.json')
        continuation.run('benchmark_feed_matrix_gemma_20261031.py','gemma4_12b_llamacpp','study-gemma4-12b-q4:20261031')
        stages.state('all_models_verified',labels=['qwen3_8b','qwen35_9b_llamacpp','gemma4_12b_llamacpp'],timed_inferences=5400)
    except Exception as error:
        stages.state('blocked',error=str(error));raise


if __name__=='__main__':main()
