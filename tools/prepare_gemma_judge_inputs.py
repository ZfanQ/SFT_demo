#!/usr/bin/env python3
"""Freeze same-PDF full-text inputs for a separate Gemma GPT scoring run."""
import gzip
import hashlib
import json
import os
from pathlib import Path

import pymupdf


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    os.umask(0o002)
    root = Path('/data/SFT_demo/Oct')
    out = root / 'results/gemma_gpt_scores_20261023'
    out.mkdir(exist_ok=False)
    out.chmod(0o2775)
    prior = {r['paper_id']: r for r in json.loads((root / 'GPT_eval/inputs.json').read_text())}
    manifest, pairs = [], []
    for n in range(1, 201):
        pid = f'paper{n:03d}'
        pdf = root / 'All_papers/paper' / f'{pid}.pdf'
        summary = root / 'All_papers/summary_gemma' / f'summary_gemma_{pid}.txt'
        raw_pdf, raw_summary = pdf.read_bytes(), summary.read_bytes()
        if sha(raw_pdf) != prior[pid]['paper_sha256']:
            raise ValueError(f'PDF changed since Qwen evaluation: {pid}')
        with pymupdf.open(stream=raw_pdf, filetype='pdf') as doc:
            pages = [page.get_text(sort=True) for page in doc]
        record = {'paper_id': pid, 'paper_path': str(pdf), 'summary_path': str(summary),
                  'paper_sha256': sha(raw_pdf), 'summary_sha256': sha(raw_summary),
                  'summary_words': len(raw_summary.decode().split()), 'pages': len(pages),
                  'extracted_characters': sum(len(p) for p in pages),
                  'pages_text_sha256': sha(json.dumps(pages, ensure_ascii=False).encode()),
                  'sparse_text_pages': [i + 1 for i, p in enumerate(pages) if len(p.strip()) < 30]}
        if not 0 < record['summary_words'] <= 250:
            raise ValueError(f'Invalid summary: {pid}')
        if record['pages'] != prior[pid]['pages'] or record['extracted_characters'] != prior[pid]['extracted_characters']:
            raise ValueError(f'PDF extraction differs from prior Qwen setup: {pid}')
        pairs.append({**record, 'summary_text': raw_summary.decode(), 'pages_text': pages})
        manifest.append(record)
    for record in manifest:
        if sha(Path(record['paper_path']).read_bytes()) != record['paper_sha256'] or sha(Path(record['summary_path']).read_bytes()) != record['summary_sha256']:
            raise ValueError('Inputs changed during snapshot')
    (out / 'inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with gzip.open(out / 'source_pairs.jsonl.gz', 'wt') as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + '\n')
    print(f'Prepared {len(manifest)} verified complete-PDF/Gemma pairs in {out}')


if __name__ == '__main__':
    main()
