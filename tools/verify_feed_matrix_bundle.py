#!/usr/bin/env python3
"""Final cross-model audit of a complete, locally copied feed-matrix bundle."""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex

spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('analyze_feed_matrix.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    root=parser.parse_args().root
    labels=['qwen3_8b','qwen35_9b_llamacpp','gemma4_12b_llamacpp']
    hashes=set();intervals=[];results=[]
    for label in labels:
        result=audit.analyze(root,label);results.append(result)
        assert result['state']=='verified_complete' and result['timed_requests']==1800
        hashes.add(result['dataset_sha256'])
        folder=root/label;protocol=json.loads((folder/'protocol.json').read_text())
        assert protocol['script_sha256']==sha(root/'source/benchmark_feed_matrix.py')
        if label!='qwen3_8b':
            provenance=result['backend']
            assert provenance['driver_sha256']==sha(folder/'driver_source.py')
            if label=='gemma4_12b_llamacpp':
                assert provenance['round_helper_sha256']==sha(folder/'round_helper_source.py')
            setup=json.loads((root/f'{label}_model_setup.json').read_text())
            actual=shlex.split(next(x for x in setup['show']['modelfile'].splitlines() if x.startswith('FROM ')))[1]
            assert actual==provenance['model_path']
        for round_result in result['rounds']:
            rows=[json.loads(line) for line in (folder/round_result['attempt']/'responses.jsonl').read_text().splitlines()]
            start=min(datetime.fromisoformat(row['request_started_utc']) for row in rows)
            end=max(datetime.fromisoformat(row['finished_utc']) for row in rows)
            intervals.append((start,end,label,round_result['profile_id'],round_result['parallel']))
    assert len(hashes)==1 and len(intervals)==27
    ordered=sorted(intervals)
    assert all(previous[1]<=following[0] for previous,following in zip(ordered,ordered[1:])), 'Measured rounds overlap'
    result={'state':'verified_complete','models':labels,'model_matrices':3,'accepted_rounds':27,
            'valid_timed_requests':5400,'unique_paper_profile_inputs':600,'frozen_abstracts':200,
            'dataset_sha256':hashes.pop(),'measured_round_intervals_do_not_overlap':True,
            'independent_relevance_gold_labels':False,
            'note':'Runtime service shutdown and server-side permissions are recorded separately in server_final_checks.json.'}
    (root/'audit_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
