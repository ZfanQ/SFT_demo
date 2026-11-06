#!/usr/bin/env python3
"""Export evidence and model suspicions with explicitly blank human verdicts."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

FIELDS=['finding_id','paper_id','source','candidate_id','review_origin','review_status','priority',
        'candidate_quote','reference_quote','pdf_page','explanation','source_hash_match',
        'pdf_link','evidence_file','human_verdict','human_reason','reviewer','reviewed_at']


def identifier(row):
    value='|'.join(str(row.get(k,'')) for k in ['paper_id','source','candidate_id','review_origin','candidate_quote','reference_quote','pdf_page'])
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def build(root,history):
    manifest=json.loads((root/'inputs/manifest.json').read_text())
    papers={r['paper_id']:r for r in manifest['papers']}
    mapping=json.loads((root/'inputs/blinding_map.json').read_text());rows=[]
    old=history/'followup_20261020/fulltext_adjudication'
    oldmap=json.loads((old/'manifest.json').read_text())['inputs']
    old_reviewed=set();historical_records=[]
    for path in sorted(old.glob('batch_*.json')):
        historical=json.loads(path.read_text())
        historical_records.append({'original_file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'record':historical})
        for paper in historical['result']['papers']:
            pid=paper['paper_id'];old_reviewed.add(pid)
            for candidate in paper['candidates']:
                source=oldmap[pid]['label_map'][candidate['label']]
                match=papers[pid]['historical_hash_matches'][source]
                for f in candidate['findings']:
                    rows.append({'paper_id':pid,'source':source,'candidate_id':candidate['label'],
                        'review_origin':'historical_fulltext_20261020','review_status':'automated_'+f['severity'],
                        'priority':'high' if f['severity']=='major' else 'medium',
                        'candidate_quote':f['candidate_quote'],'reference_quote':f['reference_quote'],
                        'pdf_page':'','explanation':f['explanation'],'source_hash_match':match,
                        'evidence_file':'../inputs/historical_evidence.json'})
    flags=[]
    for item in map(json.loads,(history/'gemma_evaluation_20261023/gpt_scores/evaluations.jsonl').read_text().splitlines()):
        if not item['major_factual_error']:continue
        pid=item['paper_id'];flags.append(pid)
        rows.append({'paper_id':pid,'source':'gemma','candidate_id':'','review_origin':'historical_scores_only_20261023',
            'review_status':'needs_evidence_review','priority':'high','candidate_quote':'','reference_quote':'','pdf_page':'',
            'explanation':'Numeric flag only; not an evidence-backed error finding.',
            'source_hash_match':item['summary_sha256']==papers[pid]['sources']['gemma']['sha256'],
            'evidence_file':'../inputs/historical_evidence.json'})
    scores_file=history/'gemma_evaluation_20261023/gpt_scores/evaluations.jsonl'
    (root/'inputs/historical_evidence.json').write_text(json.dumps({
        'historical_fulltext_reviews':historical_records,
        'gemma_numeric_ledger_sha256':hashlib.sha256(scores_file.read_bytes()).hexdigest(),
        'gemma_numeric_reviews':[json.loads(line) for line in scores_file.read_text().splitlines()]},indent=2)+'\n')
    active=root/'gpt_evidence/active_review.json'
    calibration=root/'gpt_evidence'/json.loads(active.read_text())['folder'] if active.exists() else root/'gpt_evidence/calibration_v1'
    reviews=[]
    for path in sorted(calibration.glob('paper???_?.json')):
        item=json.loads(path.read_text());r=item['result'];pid=r['paper_id'];source=mapping[pid][r['candidate_id']]
        reviews.append({**r,'source':source})
        for f in r['findings']:
            rows.append({'paper_id':pid,'source':source,'candidate_id':r['candidate_id'],
                'review_origin':calibration.name+'_fulltext_20261031','review_status':f['status'],
                'priority':'high' if f['severity']=='major' else 'medium',
                'candidate_quote':f['candidate_quote'],'reference_quote':f['reference_quote'],'pdf_page':f['pdf_page'],
                'explanation':f['explanation'],'source_hash_match':item['metadata']['candidate_sha256']==papers[pid]['sources'][source]['sha256'],
                'evidence_file':f'../gpt_evidence/{calibration.name}/{path.name}'})
    reviewed_gemma={r['paper_id'] for r in reviews if r['source']=='gemma'}
    for row in rows:
        if row['review_origin']=='historical_scores_only_20261023' and row['paper_id'] in reviewed_gemma:
            row['review_status']='numeric_flag_evidence_review_available'
            row['explanation']='Historical numeric flag only; a separate new evidence review is available. See that review; this row is not an additional factual finding.'
    target=root/'human_review/queue.csv';target.parent.mkdir(exist_ok=True)
    previous={}
    if target.exists():
        with target.open() as stream:previous={r['finding_id']:r for r in csv.DictReader(stream)}
    for row in rows:
        row['finding_id']=identifier(row);pid=row['paper_id']
        row['pdf_link']=f'../inputs/pdfs/{pid}.pdf' if (root/'inputs/pdfs'/f'{pid}.pdf').exists() else papers[pid]['pdf_path']
        prior=previous.get(row['finding_id'],{})
        for field in ['human_verdict','human_reason','reviewer','reviewed_at']:row[field]=prior.get(field,'')
    assert len({r['finding_id'] for r in rows})==len(rows),'Duplicate findings'
    with target.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    selected=json.loads((root/'inputs/selection.json').read_text())
    summary={'inventory_papers':200,'prior_fulltext_papers':len(old_reviewed),'gemma_scores_only_flags':len(flags),
        'calibration_papers':len(selected['calibration_ids']),'expected_candidate_reviews':20,
        'completed_candidate_reviews':len(reviews),'new_findings':sum(len(r['findings']) for r in reviews),
        'new_contradicted_findings':sum(f['status']=='contradicted' for r in reviews for f in r['findings']),
        'human_confirmed_findings':sum(r['human_verdict']=='confirmed_error' for r in rows),
        'human_reviewed_findings':sum(bool(r['human_verdict']) for r in rows),'queue_rows':len(rows),
        'unflagged_controls_reserved':len(selected['independent_unflagged_controls']),
        'state':'awaiting_independent_human_calibration' if len(reviews)==20 else 'automated_pilot_in_progress'}
    (root/'progress.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# Factuality Review: Evidence Pilot and Human Calibration','',
        'This report separates automated suspicions from human decisions. Original PDFs and summaries remain unchanged.','',
        '## Coverage','',f'- Frozen papers: 200. Historical Qwen/GPT full-text review: {len(old_reviewed)} selected papers.',
        '- Historical Gemma scores-only flags: 20. These flags are not confirmed errors.',
        f'- New blinded calibration: {len(reviews)}/20 candidate reviews, across 10 selected papers.',
        f'- New automated findings: {summary["new_findings"]}; source-contradiction labels: {summary["new_contradicted_findings"]}.',
        f'- Human-reviewed findings: {summary["human_reviewed_findings"]}; human-confirmed errors: {summary["human_confirmed_findings"]}. Zero confirmations before human review is not evidence of zero errors.',
        '- Twenty separate historically unflagged control papers were selected before new reviews. They remain reserved for independent human reading.',
        f'- Review queue: {len(rows)} rows, including historical findings, numeric flags and new findings. These overlap and are not a count of unique errors or affected summaries.','',
        '## Human review workflow','',
        'Start with [the blinded packet](human_review/packet_en.md) and record independent decisions in `human_review/independent_pilot.csv`, saving a separate copy per reviewer. Do not open GPT findings or the private mapping first. Then reconcile source evidence using `human_review/queue.csv`. Candidate labels differ by paper.','',
        'The queue contains older source-quoted findings, historical numeric flags without evidence, and any new page-linked findings. A blank human verdict means unreviewed. A source hash mismatch invalidates direct reuse. Historical exact quotations were not independently page-indexed by the old protocol and require PDF location checking.','',
        '## New automated findings','',
        '| Paper | Blinded candidate | Status | Priority | PDF page | Candidate claim |',
        '| --- | --- | --- | --- | ---: | --- |']
    for row in rows:
        if row['review_origin']!=calibration.name+'_fulltext_20261031':continue
        quote=row['candidate_quote'].replace('|','/').replace('\n',' ')
        lines.append(f'| {row["paper_id"]} | {row["candidate_id"]} | {row["review_status"]} | {row["priority"]} | {row["pdf_page"]} | {quote} |')
    lines+=['','Exact quotations and page provenance are automatically checked against supplied text. That does not validate the model\'s interpretation; humans must check context, numbers, tables, figures and uncertainty.', '',
        'This pilot is deliberately enriched with five previously flagged and five unflagged Gemma papers. It cannot estimate overall error rates or establish a model ranking. GPT-family judgments may favor related models; reference summaries are not factual gold labels.','',
        '## Extraction correction and execution audit','',
        'A bounded initial trial exposed interleaved columns in the historical PDF extraction. The ten calibration PDFs were re-extracted in reading order, with original file hashes and PDF page counts preserved. The old text and trial outputs remain archived; only the separately versioned active protocol contributes to this report. See [optimization notes](optimization_notes_en.md), `inputs/reading_order_checks.json`, and `verification.json`.','',
        '## Next gate','',
        'Obtain independent human calibration and resolve systematic reviewer failures before extending the new evidence protocol to all 200 Gemma summaries. Apply and audit the corrected extraction method before that expansion. Do not auto-correct source summaries. Preserve older and new protocols separately. This run does not change or validate the separate relevance-throughput experiment.']
    (root/'report_en.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--history',type=Path,default=Path('docs'));args=parser.parse_args();build(args.root,args.history)
