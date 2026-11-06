#!/usr/bin/env python3
"""Create a separate reading-order extraction; preserve historical PDF text snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    root=parser.parse_args().root
    original=json.loads((root/'inputs/calibration_requests.json').read_text())
    pages={};checks=[]
    for item in original:
        pid=item['paper_id']
        if pid in pages:continue
        pdf=root/'inputs/pdfs'/f'{pid}.pdf'
        assert hashlib.sha256(pdf.read_bytes()).hexdigest()==item['pdf_sha256']
        proc=subprocess.run(['pdftotext','-enc','UTF-8',str(pdf),'-'],capture_output=True,check=True)
        text=proc.stdout.decode();parts=text.split('\f')
        if not parts[-1].strip():parts.pop()
        assert len(parts)==len(item['pages_text']),f'Page count mismatch: {pid}'
        if sum(map(len,parts))<.7*sum(map(len,item['pages_text'])):raise ValueError('Extraction unexpectedly lost text')
        pages[pid]=parts
        checks.append({'paper_id':pid,'pdf_sha256':item['pdf_sha256'],'pages':len(parts),
            'old_pages_text_sha256':item['pages_text_sha256'],
            'new_pages_text_sha256':hashlib.sha256(json.dumps(parts,ensure_ascii=False).encode()).hexdigest(),
            'old_chars':sum(map(len,item['pages_text'])),'new_chars':sum(map(len,parts)),
            'sparse_pages':[i+1 for i,p in enumerate(parts) if len(p.strip())<100]})
    # Concrete regression: the old sort=True extraction interleaves the two columns here.
    passage='All patients with DM1 were confirmed by ONT sequencing having >50 repeats.'
    assert passage in ' '.join(pages['paper019'][4].split())
    requests=[]
    for item in original:
        parts=pages[item['paper_id']]
        requests.append({**item,'pages_text':parts,
            'pages_text_sha256':hashlib.sha256(json.dumps(parts,ensure_ascii=False).encode()).hexdigest(),
            'sparse_text_pages':[i+1 for i,p in enumerate(parts) if len(p.strip())<100],
            'extraction':'Poppler pdftotext default reading order; original PDF unchanged'})
    output=root/'inputs/calibration_requests_reading_order_v3.json'
    if output.exists() and json.loads(output.read_text())!=requests:raise ValueError('Frozen re-extraction changed')
    output.write_text(json.dumps(requests,ensure_ascii=False,indent=2)+'\n')
    metadata={'method':'Poppler pdftotext default reading order, UTF-8; PDF page breaks retained',
        'poppler_version':subprocess.run(['pdftotext','-v'],capture_output=True,text=True).stderr.strip(),
        'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'motivation':'Historical PyMuPDF sort=True interleaved two-column lines in paper019; verified against sort=False and Poppler output.',
        'regression_passage_present':True,'checks':checks,
        'limitation':'Count/length checks do not certify perfect table, figure, equation or reading-order extraction for every page.'}
    (root/'inputs/reading_order_checks.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('Created separate reading-order requests; verified 10 unchanged PDFs and page counts.')


if __name__=='__main__':main()
