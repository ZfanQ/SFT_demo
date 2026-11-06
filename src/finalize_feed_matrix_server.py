#!/usr/bin/env python3
"""Record final server integrity, private-service cleanup and shared-result access."""
import argparse
from datetime import datetime,timezone
import grp
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
from urllib.request import urlopen


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    root=parser.parse_args().root.resolve()
    if root!=Path('/data/SFT_demo/Oct/results/feed_matrix_20261031'):raise ValueError('Unexpected experiment root')
    pipeline=json.loads((root/'pipeline_status.json').read_text())
    assert pipeline['phase']=='all_models_verified' and pipeline['timed_inferences']==5400
    dataset=json.loads((root/'dataset.json').read_text())
    changed=[x['paper_id'] for x in dataset['papers'] if hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()!=x['sha256']]
    assert len(dataset['papers'])==200 and not changed
    ports={}
    for port in [11437,11438]:
        with socket.socket() as connection:ports[str(port)]=connection.connect_ex(('127.0.0.1',port))!=0
    assert all(ports.values()),'A private benchmark/download service remains open'
    with urlopen('http://127.0.0.1:11434/api/version',timeout=5) as response:version=json.load(response)
    assert version['version']=='0.34.4'
    with urlopen('http://127.0.0.1:11434/api/ps',timeout=5) as response:shared=json.load(response)
    with urlopen('http://127.0.0.1:11434/api/tags',timeout=5) as response:tags=json.load(response)['models']
    baseline=json.loads((root/'qwen3_8b/protocol.json').read_text())['model']
    current=next(model for model in tags if model['name']==baseline['name'])
    assert current['digest']==baseline['digest']
    models=[]
    for label in ['qwen35_9b_llamacpp','gemma4_12b_llamacpp']:
        provenance=json.loads((root/label/'backend_provenance.json').read_text())
        digest=hashlib.sha256()
        with Path(provenance['model_path']).open('rb') as source:
            for chunk in iter(lambda:source.read(8*1024*1024),b''):digest.update(chunk)
        assert digest.hexdigest()==provenance['model_sha256']
        models.append({'label':label,'model_sha256':digest.hexdigest(),'unchanged':True})
    result={'utc':datetime.now(timezone.utc).isoformat(),'original_abstracts_checked':200,'changed_abstracts':changed,
            'private_ports_closed':ports,'shared_ollama_version':version,'shared_ollama_ps':shared,
            'original_qwen8b_tag_unchanged':True,'original_qwen8b_digest':current['digest'],
            'model_blob_rechecks':models,
            'gpu_snapshot':subprocess.check_output(['nvidia-smi'],text=True),
            'permissions':{'group':'sft','directory_mode':'2775','file_mode':'0664'},
            'scope':'Only this newly created experiment result tree receives permission changes.'}
    target=root/'server_final_checks.json';target.write_text(json.dumps(result,indent=2)+'\n')
    gid=grp.getgrnam('sft').gr_gid;paths=[root,*root.rglob('*')]
    for path in paths:
        if path.is_symlink():raise ValueError('Unexpected symlink in new result tree')
        os.chown(path,-1,gid);path.chmod(0o2775 if path.is_dir() else 0o664)
    assert all(path.stat().st_gid==gid and stat.S_IMODE(path.stat().st_mode)==(0o2775 if path.is_dir() else 0o664) for path in paths)
    result['permissions'].update(verified=True,checked_paths=len(paths))
    result['state']='verified_complete'
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'checked_abstracts':200,'changed':0,'private_services_closed':True,
                      'shared_service_healthy':True,'group_access_verified_paths':len(paths)}))


if __name__=='__main__':main()
