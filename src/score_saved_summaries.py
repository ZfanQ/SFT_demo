#!/usr/bin/env python3
"""Score saved summaries against two frozen references, without generation."""
import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)
    path.chmod(0o664)


def text_files(directory, pattern):
    result = {}
    for path in directory.glob('*.txt'):
        match = re.fullmatch(pattern, path.name)
        if not match:
            raise ValueError(f'Unexpected filename: {path}')
        number = int(match[1])
        if number in result:
            raise ValueError(f'Duplicate paper number: {number}')
        result[number] = path
    if set(result) != set(range(1, 201)):
        raise ValueError(f'{directory}: expected exactly IDs 1..200')
    return result


def snapshot(root, output):
    manifest_path = output / 'input_manifest.json'
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    groups = {
        'candidate_qwen8b': text_files(root / 'summary_Qwen8b', r'summary_Qwen8b_paper(\d+)\.txt'),
        'author_abstract': text_files(root / 'abstract', r'paper(\d+)\.txt'),
        'gpt_reference': text_files(root / 'summary_gpt6', r'summary_gpt6_paper(\d+)\.txt'),
    }
    inputs = {}
    for group, files in groups.items():
        dest = output / 'inputs' / group
        dest.mkdir(parents=True, exist_ok=True)
        dest.chmod(0o2775)
        inputs[group] = {}
        for number, source in sorted(files.items()):
            before = source.stat()
            raw = source.read_bytes()
            after = source.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError(f'Input changed while reading: {source}')
            text = raw.decode('utf-8')
            if not text.strip():
                raise ValueError(f'Empty input: {source}')
            path = dest / f'paper{number:03}.txt'
            path.write_bytes(raw)
            path.chmod(0o664)
            inputs[group][str(number)] = {
                'original_path': str(source), 'snapshot_path': str(path.relative_to(output)),
                'sha256': sha(raw), 'words': len(text.split()),
                'mtime_ns': after.st_mtime_ns,
            }
    # A frozen copy cannot silently combine files changed during the snapshot.
    for records in inputs.values():
        for record in records.values():
            if sha(Path(record['original_path']).read_bytes()) != record['sha256']:
                raise RuntimeError('Inputs changed during snapshot; start a new output directory.')
    manifest = {'created_utc': now(), 'papers': 200, 'inputs': inputs,
                'snapshot_version_sha256': sha(json.dumps(inputs, sort_keys=True).encode()),
                'note': 'Existing 200 GPT references at snapshot time; not a claim that a teammate\'s newer generation is final.'}
    save(manifest_path, manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hf-home', type=Path, required=True)
    parser.add_argument('--encoder-revision', required=True)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    output.chmod(0o2775)
    started = time.monotonic()
    manifest = snapshot(args.root, output)
    print(f'{now()} Frozen 600 files, 200 paired papers', flush=True)
    os.environ['HF_HOME'] = str(args.hf_home)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    from rouge_score import rouge_scorer
    from bert_score import BERTScorer
    import torch
    torch.set_num_threads(4)
    config = {
        'rouge_types': ['rouge1', 'rouge2', 'rougeL'], 'use_stemmer': True,
        'bertscore_model': 'roberta-large', 'num_layers': 17, 'lang': 'en',
        'idf': False, 'rescale_with_baseline': False, 'use_fast_tokenizer': False,
        'device': 'cpu', 'batch_size': 1, 'nthreads': 4,
        'normalization': 'single-space join of str.split() on both sides',
        'long_input_policy': 'ROUGE uses complete texts. Standard BERTScore tokenizer truncates to512 tokens including special tokens; affected pairs explicitly flagged; matched untruncated subset also reported.',
        'averaging': 'unweighted arithmetic mean across papers; no corpus concatenation',
        'encoder_revision': args.encoder_revision,
        'packages': {p: version(p) for p in ['torch', 'transformers', 'bert-score', 'rouge-score', 'huggingface-hub']},
        'script_sha256': sha(Path(__file__).read_bytes()),
        'input_snapshot_sha256': manifest['snapshot_version_sha256'],
    }
    print(f'{now()} Loading cached encoder on CPU; no inference generation', flush=True)
    scorer = BERTScorer(model_type='roberta-large', num_layers=17, lang='en',
                        idf=False, rescale_with_baseline=False, use_fast_tokenizer=False,
                        device='cpu', batch_size=1, nthreads=4)
    revision = getattr(scorer._model.config, '_commit_hash', None)
    if revision != args.encoder_revision:
        raise RuntimeError(f'Encoder revision mismatch: {revision}')
    config['bertscore_hash'] = scorer.hash
    config['tokenizer_limit'] = scorer._tokenizer.model_max_length
    config_path = output / 'metric_config.json'
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise RuntimeError('Configuration changed; choose a new output directory.')
    save(config_path, config)
    rouge = rouge_scorer.RougeScorer(config['rouge_types'], use_stemmer=True)
    records = {}
    for group, entries in manifest['inputs'].items():
        records[group] = {}
        for number, record in entries.items():
            raw = (output / record['snapshot_path']).read_bytes()
            if sha(raw) != record['sha256']:
                raise RuntimeError('Snapshot changed: ' + record['snapshot_path'])
            text = ' '.join(raw.decode().split())
            tokens = scorer._tokenizer.encode(text, add_special_tokens=True,
                                             add_prefix_space=True, truncation=False)
            records[group][int(number)] = (text, len(tokens))
    length_rows = [{'paper': i, 'group': group, 'tokens': nt,
                    'over_limit': nt > config['tokenizer_limit']}
                   for group, entries in records.items() for i, (_, nt) in sorted(entries.items())]
    save(output / 'token_length_check.json', length_rows)
    print(f'{now()} Length check: {sum(x["over_limit"] for x in length_rows)} /600 texts over limit', flush=True)
    ledger = output / 'per_paper.jsonl'
    completed = {}
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            row = json.loads(line)
            completed[(row['reference_type'], row['number'])] = row
    for ref_type in ['author_abstract', 'gpt_reference']:
        for number in range(1, 201):
            if (ref_type, number) in completed:
                continue
            prediction, pt = records['candidate_qwen8b'][number]
            reference, rt = records[ref_type][number]
            row = {'number': number, 'paper_id': f'paper{number:03}',
                   'model': 'qwen3:8b', 'reference_type': ref_type,
                   'candidate_sha256': manifest['inputs']['candidate_qwen8b'][str(number)]['sha256'],
                   'reference_sha256': manifest['inputs'][ref_type][str(number)]['sha256'],
                   'prediction_tokens': pt, 'reference_tokens': rt,
                   'prediction_words': len(prediction.split()), 'reference_words': len(reference.split())}
            t = time.monotonic()
            for metric, value in rouge.score(reference, prediction).items():
                row[metric + '_precision'] = value.precision
                row[metric + '_recall'] = value.recall
                row[metric + '_f1'] = value.fmeasure
            with torch.inference_mode():
                bp, br, bf = scorer.score([prediction], [reference], batch_size=1)
            row.update(bertscore_precision=bp[0].item(), bertscore_recall=br[0].item(),
                       bertscore_f1=bf[0].item(),
                       bertscore_prediction_truncated=pt > config['tokenizer_limit'],
                       bertscore_reference_truncated=rt > config['tokenizer_limit'],
                       bertscore_status='scored_standard_truncated' if max(pt, rt) > config['tokenizer_limit'] else 'scored_full_text')
            row['scoring_seconds'] = time.monotonic() - t
            row['scored_utc'] = now()
            with ledger.open('a') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())
            ledger.chmod(0o664)
            completed[(ref_type, number)] = row
            save(output / 'status.json', {'state': 'running', 'completed_pairs': len(completed),
                                         'total_pairs': 400, 'last_reference': ref_type,
                                         'last_paper': number, 'updated_utc': now()})
            if number % 10 == 0:
                print(f'{now()} {ref_type}: {number}/200; total {len(completed)}/400', flush=True)
    rows = [completed[(ref, i)] for ref in ['author_abstract', 'gpt_reference'] for i in range(1, 201)]
    with (output / 'per_paper.csv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    metric_names = ['rouge1_f1', 'rouge2_f1', 'rougeL_f1', 'bertscore_precision', 'bertscore_recall', 'bertscore_f1']
    aggregates = []
    matched = {i for i in range(1, 201)
               if all(completed[(r, i)]['bertscore_status'] == 'scored_full_text'
                      for r in ['author_abstract', 'gpt_reference'])}
    for ref in ['author_abstract', 'gpt_reference']:
        for subset in ['all_available', 'matched_full_bertscore_inputs']:
            selected = [r for r in rows if r['reference_type'] == ref and
                        (subset == 'all_available' or r['number'] in matched)]
            a = {'reference_type': ref, 'subset': subset, 'papers': len(selected)}
            for metric in metric_names:
                values = [r[metric] for r in selected if r[metric] is not None]
                a[metric] = statistics.mean(values) if values else None
                a[metric + '_n'] = len(values)
            aggregates.append(a)
    drift = []
    for group, entries in manifest['inputs'].items():
        for number, record in entries.items():
            path = Path(record['original_path'])
            if not path.exists() or sha(path.read_bytes()) != record['sha256']:
                drift.append({'group': group, 'paper': int(number), 'path': str(path)})
    save(output / 'summary.json', {'completed_utc': now(), 'model': 'qwen3:8b',
                                  'pairs': len(rows), 'aggregates': aggregates,
                                  'bertscore_overlength_pairs': [r['paper_id'] + ':' + r['reference_type'] for r in rows if r['bertscore_status'] == 'scored_standard_truncated'],
                                  'current_source_changes_since_snapshot': drift,
                                  'elapsed_seconds': time.monotonic() - started})
    lines = ['# Qwen3-8B: two-reference ROUGE / BERTScore', '',
             'The same 200 saved candidates were scored against two frozen reference sets. No model summaries were generated or changed.', '',
             '| Reference | ROUGE papers | R1 F1 | R2 F1 | RL F1 | BERTScore papers | BERTScore F1 |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for a in aggregates:
        if a['subset'] != 'all_available':
            continue
        bf = f'{a["bertscore_f1"]:.4f}' if a['bertscore_f1'] is not None else 'unavailable'
        lines.append(f'| {a["reference_type"]} | {a["rouge1_f1_n"]} | {a["rouge1_f1"]:.4f} | {a["rouge2_f1"]:.4f} | {a["rougeL_f1"]:.4f} | {a["bertscore_f1_n"]} | {bf} |')
    lines += ['', 'Scores are mean per-paper F1 on a 0–1 scale; BERTScore is unrescaled.',
              'BERTScore: roberta-large, layer17, IDF off, CPU. ROUGE: stemming on.',
              'ROUGE uses complete texts. Standard BERTScore uses at most512 tokens including special tokens. Every affected pair is flagged in CSV/JSON.',
              f'Cross-reference matched BERTScore subset: {len(matched)} papers; aggregates are in summary.json.',
              'Author abstracts retain their published section labels and registration text. Only whitespace was normalized.',
              'GPT references are the pre-existing 200-file snapshot, with mixed generation provenance; a teammate\'s newer output is a separate reference version.',
              f'Files changed outside this frozen run during scoring: {len(drift)}. Results still refer only to the saved snapshot.',
              'Overlap/semantic similarity metrics are not an independent full-paper factuality assessment.']
    (output / 'results.md').write_text('\n'.join(lines) + '\n')
    for filename in ['per_paper.csv', 'results.md']:
        (output / filename).chmod(0o664)
    save(output / 'status.json', {'state': 'completed', 'completed_pairs': 400,
                                 'total_pairs': 400, 'updated_utc': now()})
    print(f'{now()} COMPLETE: {output / "results.md"}', flush=True)


if __name__ == '__main__':
    main()
