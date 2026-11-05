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
    lines=['# Factuality Review: Source-Linked GPT Calibration','',
        f'Source-blinded GPT review of {len(reviews)} saved summaries across 10 papers produced '
        f'**{summary["new_findings"]} concerns**, including **{summary["new_contradicted_findings"]} source-contradiction labels**. '
        'Source quotations and PDF-page checks support a review queue ready for independent human calibration.','',
        '## Coverage','',f'- Frozen papers: 200. Historical Qwen/GPT full-text review: {len(old_reviewed)} selected papers.',
        '- Historical Gemma scores-only flags: 20, used to guide sample selection.',
        f'- Source-blinded calibration: {len(reviews)}/20 candidate reviews across 10 papers.',
        f'- Human-reviewed finding rows: {summary["human_reviewed_findings"]}; recorded human-confirmed errors: {summary["human_confirmed_findings"]}.',
        '- Twenty additional historically unflagged control papers were selected before review and reserved for independent human reading.',
        f'- Review queue: {len(rows)} records spanning historical findings, numeric flags and new concerns. Article-level counts require deduplication of overlapping records.','',
        '## Method','',
        'Five previously Gemma-flagged and five unflagged papers each contribute saved Qwen and Gemma summaries. '
        'Each GPT session receives one anonymous candidate and its full article. Candidate labels vary by paper; model identities and prior scores are hidden.','',
        'Automated validation checks the candidate quotation and the cited source text on the specified PDF page. '
        'The review distinguishes contradictions from unsupported or uncertain claims. Original PDFs and summaries remain unchanged.','',
        '## Automated concerns','',
        '| Paper | Blinded candidate | Status | Priority | PDF page | Candidate claim |',
        '| --- | --- | --- | --- | ---: | --- |']
    for row in rows:
        if row['review_origin']!=calibration.name+'_fulltext_20261031':continue
        quote=row['candidate_quote'].replace('|','/').replace('\n',' ')
        lines.append(f'| {row["paper_id"]} | {row["candidate_id"]} | {row["review_status"]} | {row["priority"]} | {row["pdf_page"]} | {quote} |')
    lines+=['','## Extraction improvement and verification','',
        'Reading-order re-extraction corrected interleaved PDF columns for the ten papers while preserving PDF hashes and page counts. '
        'Results use the revised text; earlier diagnostics remain archived. '
        'See [optimization notes](optimization_notes_en.md), `inputs/reading_order_checks.json`, and `verification.json`.','',
        '## Interpretation and human calibration','',
        'Independent readers assess whether the source context supports each GPT concern and whether it materially changes the summary. '
        'Human calibration is pending; recorded confirmations remain zero.','',
        'The enriched sample supports workflow calibration and case analysis. Population error rates and model rankings require appropriately sampled evaluation. '
        'GPT-family reviewer preferences are a potential bias, including for GPT-written references.','',
        '## Human review procedure','',
        '1. Read [the blinded packet](human_review/packet_en.md) and PDFs before consulting GPT findings or source mappings. Each reviewer records judgments in a separate copy of `human_review/independent_pilot.csv`.',
        '2. Reconcile judgments with `human_review/queue.csv`; record confirmed, rejected or unresolved concerns and supporting context.',
        '3. Locate unindexed historical quotations in the PDFs and verify source hashes before reusing judgments. '
        'Blank human-verdict fields remain unreviewed.', '',
        '## Next steps','',
        'Resolve reviewer false alarms, misses and systematic interpretation problems through independent calibration. '
        'Then audit corrected extraction across the 200 Gemma papers and extend the evidence review. '
        'Preserve protocol versions and save any edited summaries as separate outputs.']
    (root/'report_en.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--history',type=Path,default=Path('docs'));args=parser.parse_args();build(args.root,args.history)
