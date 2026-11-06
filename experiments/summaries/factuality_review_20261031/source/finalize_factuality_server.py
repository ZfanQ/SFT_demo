#!/usr/bin/env python3
"""Verify unchanged source files and group access only inside the new factuality result tree."""
import argparse
from datetime import datetime,timezone
import grp
import hashlib
import json
import os
from pathlib import Path
import stat


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    root=parser.parse_args().root.resolve()
    if root!=Path('/data/SFT_demo/Oct/results/factuality_review_20261031'):raise ValueError('Unexpected result path')
    papers=json.loads((root/'inputs/manifest.json').read_text())['papers']
    assert len(papers)==200
    changes=[];checked=0
    for paper in papers:
        if sha(Path(paper['pdf_path']))!=paper['pdf_sha256']:changes.append(paper['paper_id']+':pdf')
        checked+=1
        for label,source in paper['sources'].items():
            if sha(Path(source['path']))!=source['sha256']:changes.append(paper['paper_id']+':'+label)
            checked+=1
    assert checked==1000 and not changes,'Original files changed'
    result={'state':'verified_complete','utc':datetime.now(timezone.utc).isoformat(),
        'original_pdfs_checked':200,'original_text_files_checked':800,'changed':changes,
        'permissions_scope':'Only the new factuality_review_20261031 result tree',
        'group':'sft','directory_mode':'2775','file_mode':'0664',
        'report_sha256':sha(root/'report_en.md'),'human_packet_sha256':sha(root/'human_review/packet_en.md'),
        'human_review_is_pending':True,'no_original_summary_rewrites':True}
    target=root/'server_final_checks.json';target.write_text(json.dumps(result,indent=2)+'\n')
    gid=grp.getgrnam('sft').gr_gid;paths=[root,*root.rglob('*')]
    for path in paths:
        if path.is_symlink():raise ValueError('Unexpected symlink')
        os.chown(path,-1,gid);path.chmod(0o2775 if path.is_dir() else 0o664)
    assert all(p.stat().st_gid==gid and stat.S_IMODE(p.stat().st_mode)==(0o2775 if p.is_dir() else 0o664) for p in paths)
    result.update(group_access_verified=True,result_paths_checked=len(paths))
    target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
