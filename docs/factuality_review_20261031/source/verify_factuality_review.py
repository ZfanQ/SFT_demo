#!/usr/bin/env python3
"""Independently audit the blinded pilot, snapshot provenance and editable human queue."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from review_summary_factuality import validate_review
from prepare_factuality_triage import selection


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    root=p.parse_args().root
    manifest=json.loads((root/'inputs/manifest.json').read_text())
    snapshot=root/'inputs/source_snapshot.jsonl.gz'
    assert sha(snapshot.read_bytes())==manifest['snapshot_sha256']
    with gzip.open(snapshot,'rt') as stream:papers=[json.loads(line) for line in stream]
    assert len(papers)==200 and len({r['paper_id'] for r in papers})==200
    for paper in papers:
        for source in paper['sources'].values():assert sha(source['text'].encode())==source['sha256']
        assert sha(json.dumps(paper['pages_text'],ensure_ascii=False).encode())==paper['pages_text_sha256']
    selected=json.loads((root/'inputs/selection.json').read_text())
    historical=json.loads((root/'inputs/historical_evidence.json').read_text())
    assert selected==selection({r['paper_id'] for r in historical['gemma_numeric_reviews'] if r['major_factual_error']})
    assert len(selected['calibration_ids'])==10 and len(selected['independent_unflagged_controls'])==20
    assert not set(selected['calibration_ids'])&set(selected['independent_unflagged_controls'])
    items=json.loads((root/'inputs/calibration_requests_reading_order_v3.json').read_text())
    assert len(items)==20 and len({(r['paper_id'],r['candidate_id']) for r in items})==20
    paper_map={r['paper_id']:r for r in manifest['papers']}
    blind=json.loads((root/'inputs/blinding_map.json').read_text())
    for item in items:
        pdf=root/'inputs/pdfs'/f'{item["paper_id"]}.pdf'
        assert sha(pdf.read_bytes())==item['pdf_sha256']==paper_map[item['paper_id']]['pdf_sha256']
        assert sha(json.dumps(item['pages_text'],ensure_ascii=False).encode())==item['pages_text_sha256']
        assert sha(item['candidate'].encode())==item['candidate_sha256']
        source=blind[item['paper_id']][item['candidate_id']]
        assert item['candidate_sha256']==paper_map[item['paper_id']]['sources'][source]['sha256']
    active=json.loads((root/'gpt_evidence/active_review.json').read_text());folder=root/'gpt_evidence'/active['folder']
    protocol=json.loads((folder/'protocol.json').read_text())
    assert protocol['driver_sha256']==sha((root/'source/review_summary_factuality.py').read_bytes())
    assert protocol['fingerprint']==sha(json.dumps({k:v for k,v in protocol.items() if k!='fingerprint'},sort_keys=True).encode())
    assert protocol['requests_sha256']==sha((root/'inputs/calibration_requests_reading_order_v3.json').read_bytes())
    assert protocol['extraction_checks_sha256']==sha((root/'inputs/reading_order_checks.json').read_bytes())
    assert protocol['fingerprint']==active['fingerprint']
    reviews=[];attempts=0;invalid=0
    for item in items:
        path=folder/f'{item["paper_id"]}_{item["candidate_id"]}.json'
        if not path.exists():continue
        record=json.loads(path.read_text());metadata=record['metadata']
        assert metadata['judge_model_requested']==protocol['model'] and metadata['reasoning_effort']==protocol['reasoning_effort']
        assert record['fingerprint']==protocol['fingerprint']
        validate_review(record['result'],item)
        for key in ['candidate_sha256','pdf_sha256','pages_text_sha256']:assert metadata[key]==item[key]
        final=metadata['attempts'][-1]['attempt'];prefix=f'{item["paper_id"]}_{item["candidate_id"]}.attempt{final:02d}'
        assert sha((folder/f'{prefix}.request.txt').read_bytes())==metadata['request_sha256']
        assert json.loads((folder/f'{prefix}.response.json').read_text())==record['result']
        events=[json.loads(line) for line in (folder/f'{prefix}.events.jsonl').read_text().splitlines() if line.strip().startswith('{')]
        assert any(e['type']=='turn.completed' for e in events)
        assert not any(e.get('item',{}).get('type') in ['command_execution','mcp_tool_call','web_search','collab_tool_call'] for e in events)
        attempts+=len(metadata['attempts']);invalid+=sum(not a['valid'] for a in metadata['attempts'])
        reviews.append(record['result'])
    with (root/'human_review/queue.csv').open() as stream:queue=list(csv.DictReader(stream))
    assert len(queue)==len({r['finding_id'] for r in queue})
    with (root/'human_review/independent_pilot.csv').open() as stream:independent=list(csv.DictReader(stream))
    assert len(independent)==20
    expected={(r['paper_id'],r['candidate_id']):r for r in items}
    assert {(r['paper_id'],r['candidate_id']) for r in independent}==set(expected)
    for row in independent:
        assert row['candidate_text']==expected[(row['paper_id'],row['candidate_id'])]['candidate']
    human=sum(bool(r['human_verdict']) for r in independent)
    result={'state':'verified_calibration_complete' if len(reviews)==20 else 'verified_partial',
        'snapshot_papers':200,'source_text_hashes_checked':800,'original_pdf_hashes_checked':10,
        'accepted_candidate_reviews':len(reviews),'accepted_review_attempts':attempts,
        'rejected_attempts_in_active_protocol':invalid,'automated_findings':sum(len(r['findings']) for r in reviews),
        'independent_human_reviews_recorded':human,'human_calibration_complete':human==20,
        'factual_correctness_certified':False,'ready_for_200_paper_expansion':False,
        'note':'Complete independent human calibration and resolve systematic issues before expansion.'}
    (root/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
