#!/usr/bin/env python3
"""Direct GPT-summary/author-abstract agreement on a previous frozen dataset."""
import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)
    path.chmod(0o664)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--previous-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hf-home', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o2775)
    prior = json.loads((args.previous_run / 'input_manifest.json').read_text())
    config = json.loads((args.previous_run / 'metric_config.json').read_text())
    groups = ['author_abstract', 'gpt_reference']
    frozen = {}
    for group in groups:
        entries = prior['inputs'][group]
        if set(map(int, entries)) != set(range(1, 201)):
            raise ValueError('Expected200 paired references')
        dest = out / 'inputs' / group
        dest.mkdir(parents=True, exist_ok=True)
        dest.chmod(0o2775)
        frozen[group] = {}
        for number, record in entries.items():
            raw = (args.previous_run / record['snapshot_path']).read_bytes()
            if sha(raw) != record['sha256']:
                raise ValueError('Previous frozen input changed: ' + record['snapshot_path'])
            target = dest / f'paper{int(number):03}.txt'
            if target.exists() and target.read_bytes() != raw:
                raise ValueError('Current run snapshot changed; choose a new output directory')
            if not target.exists():
                target.write_bytes(raw)
                target.chmod(0o664)
            frozen[group][number] = dict(record, snapshot_path=str(target.relative_to(out)))
    save(out / 'input_manifest.json', {'created_utc': now(), 'papers': 200,
                                     'previous_run': str(args.previous_run),
                                     'previous_snapshot_sha256': prior['snapshot_version_sha256'],
                                     'candidate_group': 'gpt_reference', 'reference_group': 'author_abstract',
                                     'inputs': frozen})
    os.environ.update(HF_HOME=str(args.hf_home), HF_HUB_OFFLINE='1',
                      TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    from bert_score import BERTScorer
    from rouge_score import rouge_scorer
    import torch
    torch.set_num_threads(config['nthreads'])
    print(now(), 'Loading same cached CPU encoder; scoring200 direct pairs', flush=True)
    scorer = BERTScorer(model_type=config['bertscore_model'], num_layers=config['num_layers'],
                        lang=config['lang'], idf=config['idf'],
                        rescale_with_baseline=config['rescale_with_baseline'],
                        use_fast_tokenizer=config['use_fast_tokenizer'], device=config['device'],
                        batch_size=config['batch_size'], nthreads=config['nthreads'])
    if scorer.hash != config['bertscore_hash']:
        raise ValueError('BERTScore configuration differs from previous evaluation')
    if getattr(scorer._model.config, '_commit_hash', None) != config['encoder_revision']:
        raise ValueError('Encoder revision differs from previous evaluation')
    packages = {p: version(p) for p in config['packages']}
    if packages != config['packages']:
        raise ValueError('Software versions changed; comparison requires a new protocol')
    config.update(script_sha256=sha(Path(__file__).read_bytes()),
                  input_snapshot_sha256=prior['snapshot_version_sha256'],
                  direction='GPT summary as candidate; author abstract as reference')
    save(out / 'metric_config.json', config)
    rouge = rouge_scorer.RougeScorer(config['rouge_types'], use_stemmer=config['use_stemmer'])
    ledger = out / 'per_paper.jsonl'
    done = {}
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            row = json.loads(line)
            done[row['number']] = row
    for i in range(1, 201):
        if i in done:
            continue
        texts = {}
        for group in groups:
            record = frozen[group][str(i)]
            raw = (out / record['snapshot_path']).read_bytes()
            if sha(raw) != record['sha256']:
                raise ValueError('Frozen baseline input changed')
            text = ' '.join(raw.decode('utf-8').split())
            count = len(scorer._tokenizer.encode(text, add_special_tokens=True,
                                                add_prefix_space=True, truncation=False))
            texts[group] = (text, count)
        candidate, ct = texts['gpt_reference']
        reference, rt = texts['author_abstract']
        row = {'number': i, 'paper_id': f'paper{i:03}',
               'candidate_type': 'gpt_reference', 'reference_type': 'author_abstract',
               'candidate_sha256': frozen['gpt_reference'][str(i)]['sha256'],
               'reference_sha256': frozen['author_abstract'][str(i)]['sha256'],
               'candidate_words': len(candidate.split()), 'reference_words': len(reference.split()),
               'candidate_tokens': ct, 'reference_tokens': rt}
        t = time.monotonic()
        for name, value in rouge.score(reference, candidate).items():
            row.update({name + '_precision': value.precision,
                        name + '_recall': value.recall, name + '_f1': value.fmeasure})
        with torch.inference_mode():
            bp, br, bf = scorer.score([candidate], [reference], batch_size=config['batch_size'])
        truncated = max(ct, rt) > config['tokenizer_limit']
        row.update(bertscore_precision=bp[0].item(), bertscore_recall=br[0].item(),
                   bertscore_f1=bf[0].item(), candidate_truncated=ct > config['tokenizer_limit'],
                   reference_truncated=rt > config['tokenizer_limit'],
                   bertscore_status='scored_standard_truncated' if truncated else 'scored_full_text',
                   scoring_seconds=time.monotonic() - t, scored_utc=now())
        with ledger.open('a') as f:
            f.write(json.dumps(row) + '\n')
            f.flush()
            os.fsync(f.fileno())
        ledger.chmod(0o664)
        done[i] = row
        save(out / 'status.json', {'state': 'running', 'completed_pairs': len(done),
                                  'total_pairs': 200, 'updated_utc': now()})
        if i % 20 == 0:
            print(now(), f'{i}/200 pairs scored', flush=True)
    rows = [done[i] for i in range(1, 201)]
    with (out / 'per_paper.csv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (out / 'per_paper.csv').chmod(0o664)
    metrics = ['rouge1_f1', 'rouge2_f1', 'rougeL_f1',
               'bertscore_precision', 'bertscore_recall', 'bertscore_f1']
    assert all(all(math.isfinite(r[k]) and 0 <= r[k] <= 1 for k in metrics) for r in rows)
    aggregates = []
    for name, selected in [('all_available', rows),
                           ('matched_full_bertscore_inputs', [r for r in rows if r['bertscore_status'] == 'scored_full_text'])]:
        aggregates.append(dict(subset=name, papers=len(selected),
                               **{k: statistics.mean(r[k] for r in selected) for k in metrics}))
    save(out / 'summary.json', {'completed_utc': now(), 'pairs': 200,
                               'candidate_type': 'gpt_reference', 'reference_type': 'author_abstract',
                               'aggregates': aggregates,
                               'bertscore_overlength_papers': [r['paper_id'] for r in rows if r['bertscore_status'] != 'scored_full_text'],
                               'elapsed_seconds': time.monotonic() - started,
                               'same_reference_files_as_previous_qwen_run': True})
    save(out / 'status.json', {'state': 'completed', 'completed_pairs': 200,
                              'total_pairs': 200, 'updated_utc': now()})
    print(now(), 'COMPLETE', json.dumps(aggregates), flush=True)


if __name__ == '__main__':
    main()
