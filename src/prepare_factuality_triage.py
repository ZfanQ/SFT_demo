#!/usr/bin/env python3
"""Freeze current summaries against historical PDF text and prepare blinded calibration."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import random


def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def snapshot(root,out):
    previous=root/'results/gemma_gpt_scores_20261023'
    metadata={r['paper_id']:r for r in json.loads((previous/'inputs.json').read_text())}
    with gzip.open(previous/'source_pairs.jsonl.gz','rt') as stream:
        pairs=[json.loads(line) for line in stream]
    assert len(pairs)==200 and {p['paper_id'] for p in pairs}=={f'paper{i:03d}' for i in range(1,201)}
    rows=[]
    for pair in pairs:
        pid=pair['paper_id'];m=metadata[pid]
        assert sha(json.dumps(pair['pages_text'],ensure_ascii=False).encode())==m['pages_text_sha256']
        pdf=root/'All_papers/paper'/f'{pid}.pdf'
        assert sha(pdf.read_bytes())==m['paper_sha256']==pair['paper_sha256']
        sources={}
        for label,folder,prefix in [('qwen8b','summary_Qwen8b','summary_Qwen8b_'),
                                    ('gemma','summary_gemma','summary_gemma_'),
                                    ('gpt_reference','summary_gpt6','summary_gpt6_'),
                                    ('author_abstract','abstract','')]:
            path=root/'All_papers'/folder/f'{prefix}{pid}.txt';raw=path.read_bytes()
            assert raw.strip()
            sources[label]={'text':raw.decode(),'sha256':sha(raw),'path':str(path)}
        assert sources['gemma']['sha256']==m['summary_sha256'],'Gemma summary changed from scored snapshot'
        rows.append({'paper_id':pid,'pdf_path':str(pdf),'pdf_sha256':m['paper_sha256'],
                     'pages_text_sha256':m['pages_text_sha256'],'pages_text':pair['pages_text'],
                     'sparse_text_pages':m['sparse_text_pages'],'sources':sources})
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise ValueError('Refusing to replace frozen snapshot')
    with gzip.open(out,'wt') as stream:
        for row in rows:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    print('Frozen 200 PDF-linked current summary records:',out)


def selection(flagged):
    rng=random.Random(42);all_ids={f'paper{i:03d}' for i in range(1,201)}
    flagged=sorted(flagged);unflagged=sorted(all_ids-set(flagged))
    positive=sorted(rng.sample(flagged,5));negative=sorted(rng.sample(unflagged,5))
    controls=sorted(rng.sample(sorted(set(unflagged)-set(negative)),20))
    return {'seed':42,'calibration_flagged':positive,'calibration_unflagged':negative,
            'calibration_ids':sorted(positive+negative),'independent_unflagged_controls':controls,
            'scope':'Enriched calibration, not representative error-rate estimation; labels hidden in human-first packet.'}


def prepare(snapshot_path,history,out):
    with gzip.open(snapshot_path,'rt') as stream:rows=[json.loads(line) for line in stream]
    assert len(rows)==200
    flags={r['paper_id'] for r in map(json.loads,(history/'gemma_evaluation_20261023/gpt_scores/evaluations.jsonl').read_text().splitlines()) if r['major_factual_error']}
    chosen=selection(flags)
    old=json.loads((history/'followup_20261020/fulltext_adjudication/manifest.json').read_text())
    manifest=[];blind={};requests=[]
    for row in rows:
        pid=row['paper_id'];prior=old['inputs'][pid]
        matches={label:row['sources'][label]['sha256']==prior['summary_hashes'][label]['sha256']
                 for label in ['qwen8b','gpt_reference','author_abstract']}
        assert row['pdf_sha256']==prior['pdf_sha256']
        manifest.append({'paper_id':pid,'pdf_path':row['pdf_path'],'pdf_sha256':row['pdf_sha256'],
                         'pages_text_sha256':row['pages_text_sha256'],'sparse_text_pages':row['sparse_text_pages'],
                         'sources':{k:{a:b for a,b in v.items() if a!='text'} for k,v in row['sources'].items()},
                         'historical_hash_matches':matches})
        if pid not in chosen['calibration_ids']:continue
        labels=['qwen8b','gemma'];random.Random('factuality-v1-'+pid).shuffle(labels)
        blind[pid]=dict(zip(['A','B'],labels))
        for label,source in blind[pid].items():
            request={'paper_id':pid,'candidate_id':label,'candidate':row['sources'][source]['text'],
                     'candidate_sha256':row['sources'][source]['sha256'],'pdf_sha256':row['pdf_sha256'],
                     'pages_text_sha256':row['pages_text_sha256'],'pages_text':row['pages_text'],
                     'sparse_text_pages':row['sparse_text_pages']}
            requests.append(request)
    manifest_doc={'snapshot_sha256':sha(snapshot_path.read_bytes()),'papers':manifest}
    out.mkdir(parents=True,exist_ok=True)
    frozen=out/'inputs/manifest.json'
    if frozen.exists() and json.loads(frozen.read_text())!=manifest_doc:raise ValueError('Frozen inputs changed')
    save(frozen,manifest_doc);save(out/'inputs/selection.json',chosen);save(out/'inputs/blinding_map.json',blind)
    save(out/'inputs/calibration_requests.json',requests)
    human=out/'human_review';human.mkdir(exist_ok=True)
    import csv
    path=human/'independent_pilot.csv'
    if not path.exists():
        with path.open('w',newline='') as stream:
            fields=['paper_id','candidate_id','candidate_text','local_pdf','human_verdict','candidate_quote','evidence_page','evidence_quote','reason','reviewer','reviewed_at']
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            for r in requests:writer.writerow({'paper_id':r['paper_id'],'candidate_id':r['candidate_id'],
                'candidate_text':r['candidate'],'local_pdf':f'../inputs/pdfs/{r["paper_id"]}.pdf'})
    packet=['# Independent Human Calibration Packet','',
            'Read each PDF and candidate before opening GPT review outputs or the blinding map. Record your own decision in independent_pilot.csv. Blank means unreviewed; no-issue means only no issue identified, not certification. Each reviewer should save a separate copy.','']
    for pid in chosen['calibration_ids']:
        packet.extend([f'## {pid}', '',f'[Open original PDF](../inputs/pdfs/{pid}.pdf)',''])
        for r in requests:
            if r['paper_id']==pid:packet.extend([f'### Candidate {r["candidate_id"]}','',r['candidate'],''])
    (human/'packet_en.md').write_text('\n'.join(packet))
    print(json.dumps({'papers':200,'calibration_papers':10,'candidate_reviews':20,'gemma_old_flags':len(flags),
                      'historical_source_mismatches':sum(not all(x['historical_hash_matches'].values()) for x in manifest),
                      'selected':chosen},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    s=sub.add_parser('snapshot');s.add_argument('--server-root',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    q=sub.add_parser('prepare');q.add_argument('--snapshot',type=Path,required=True);q.add_argument('--history',type=Path,default=Path('docs'));q.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.action=='snapshot':snapshot(a.server_root,a.output)
    else:prepare(a.snapshot,a.history,a.output)


if __name__=='__main__':main()
