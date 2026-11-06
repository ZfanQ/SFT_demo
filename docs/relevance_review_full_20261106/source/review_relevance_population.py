#!/usr/bin/env python3
"""Extend the original blinded relevance review to all 600 paper/profile pairs."""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import fcntl
import json
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import threading
import time

import review_relevance_scores as base


def prepare(source, pilot, root, workers):
    dataset_raw = (source / 'dataset.json').read_bytes()
    dataset = json.loads(dataset_raw)
    old_manifest = json.loads((pilot / 'inputs/manifest.json').read_text())
    assert base.sha(dataset_raw) == old_manifest['source_dataset_sha256']
    for path, digest in old_manifest['source_files'].items():
        assert base.sha((source / path).read_bytes()) == digest, path
    papers = {p['paper_id']: p for p in dataset['papers']}
    profiles = {p['profile_id']: p for p in dataset['profiles']}
    items = []
    for original in dataset['inputs']:
        paper = papers[original['paper_id']]
        items.append({'paper_id': original['paper_id'], 'profile_id': original['profile_id'],
                      'interest': profiles[original['profile_id']]['interest'], 'abstract': paper['text'],
                      'original_prompt': original['prompt'], 'original_prompt_sha256': original['prompt_sha256'],
                      'original_abstract_sha256': original['abstract_sha256'],
                      'supplied_abstract_sha256': base.sha(paper['text'].encode())})
    assert len(items) == len({base.key(x) for x in items}) == 600
    random.Random(42).shuffle(items)
    by_key = {base.key(x): x for x in items}
    pilot_requests = json.loads((pilot / 'inputs/requests.json').read_text())
    pilot_protocol = json.loads((pilot / 'gpt_reviews/protocol.json').read_text())
    assert pilot_protocol['requests_sha256'] == base.sha((pilot / 'inputs/requests.json').read_bytes())
    assert pilot_protocol['driver_sha256'] == base.sha(Path(base.__file__).read_bytes())
    assert pilot_protocol['schema'] == base.schema() and pilot_protocol['model_requested'] == base.MODEL
    assert pilot_protocol['instructions'] == dataset['system'] + '\n\n' + base.REVIEW_INSTRUCTIONS
    reuse = {}
    for item in pilot_requests:
        name = base.key(item)
        assert by_key[name] == item, 'Pilot task changed: ' + name
        path = pilot / 'gpt_reviews' / f'{name}.json'
        record = json.loads(path.read_text())
        assert record['fingerprint'] == pilot_protocol['fingerprint']
        base.validate(record['result'], item)
        reuse[name] = {'result_sha256': base.sha(path.read_bytes()), 'fingerprint': record['fingerprint']}
    assert len(reuse) == 60
    rows = []
    for label in base.LABELS:
        for profile in base.PROFILES:
            for parallel in [2, 4, 8]:
                accepted = json.loads((source / label / f'{profile}_p{parallel}/accepted.json').read_text())
                assert accepted['state'] == 'completed' and accepted['valid'] == accepted['requests'] == 200
                ledger = source / label / accepted['attempt'] / 'responses.jsonl'
                for row in map(json.loads, ledger.read_text().splitlines()):
                    assert json.loads(row['response']['message']['content']) == {
                        field: row[field] for field in ['paper_id', 'profile_id', 'relevance']}
                    rows.append({'paper_id': row['paper_id'], 'profile_id': profile,
                                 'model_label': label, 'parallel': parallel, 'relevance': row['relevance']})
    assert len(rows) == 5400
    root.mkdir(parents=True, exist_ok=True)
    base.freeze(root / 'inputs/requests.json', items)
    base.freeze(root / 'inputs/source_scores.json', rows)
    base.freeze(root / 'inputs/manifest.json', {**old_manifest, 'selected_pairs': 600,
                'comparison_rows': 5400, 'cohort': 'All 200 papers and all three original profiles',
                'reused_pilot_pairs': 60, 'new_pairs': 540})
    base.freeze(root / 'inputs/pilot_protocol.json', pilot_protocol)
    base.freeze(root / 'inputs/pilot_requests.json', pilot_requests)
    base.freeze(root / 'inputs/reuse_manifest.json', reuse)
    protocol = {'version': 'full-population-relevance-review-20261106',
                'model_requested': pilot_protocol['model_requested'], 'reasoning_effort': 'medium',
                'instructions': pilot_protocol['instructions'], 'schema': pilot_protocol['schema'],
                'original_scale': pilot_protocol['original_scale'], 'single_pair_per_session': True,
                'requests_sha256': base.sha((root / 'inputs/requests.json').read_bytes()),
                'driver_sha256': base.sha(Path(__file__).read_bytes()),
                'base_driver_sha256': base.sha(Path(base.__file__).read_bytes()),
                'source_scores_sha256': base.sha((root / 'inputs/source_scores.json').read_bytes()),
                'pilot_fingerprint': pilot_protocol['fingerprint'], 'workers': workers,
                'source_scores_hidden': True, 'tools_enabled': False, 'validation_retries': 2,
                'retry_policy': 'Mechanical validation only. Service errors stop new submissions; accepted records resume.',
                'reuse_policy': 'Sixty unchanged pilot judgments and raw records; same model, task, scale and response schema.'}
    protocol['fingerprint'] = base.sha(json.dumps(protocol, sort_keys=True).encode())
    base.freeze(root / 'gpt_reviews/protocol.json', protocol)
    base.freeze(root / 'gpt_reviews/schema.json', base.schema())
    for name, metadata in reuse.items():
        for path in (pilot / 'gpt_reviews').glob(name + '.*'):
            target = root / 'gpt_reviews' / path.name
            if target.exists():
                assert target.read_bytes() == path.read_bytes(), 'Changed imported record'
            else:
                shutil.copy2(path, target)
        assert base.sha((root / 'gpt_reviews' / f'{name}.json').read_bytes()) == metadata['result_sha256']
    return items, protocol, reuse


def review_one(item, root, protocol, stop):
    if stop.is_set():
        return None
    out = root / 'gpt_reviews'
    name = base.key(item)
    request_text = protocol['instructions'] + '\n<untrusted_input>\n' + json.dumps(base.payload(item), ensure_ascii=False) + '\n</untrusted_input>'
    if len(request_text) > 50000:
        raise ValueError('Input exceeds review budget; no truncation applied')
    existing = list(out.glob(name + '.attempt*.request.txt'))
    next_number = max([int(p.name.split('.attempt')[1].split('.')[0]) for p in existing], default=0) + 1
    feedback, attempts, usage = '', [], []
    started = time.monotonic()
    for retry in range(3):
        number = next_number + retry
        prefix = out / f'{name}.attempt{number:02d}'
        response = Path(str(prefix) + '.response.json')
        assert not response.exists()
        request = request_text + feedback
        Path(str(prefix) + '.request.txt').write_text(request)
        try:
            with tempfile.TemporaryDirectory(prefix='sft-relevance-full-') as temp:
                schema = Path(temp) / 'schema.json'
                schema.write_text(json.dumps(base.schema()))
                command = [base.CLI, '-a', 'never', 'exec', '-m', protocol['model_requested'], '-s', 'read-only',
                           '--ephemeral', '--ignore-user-config', '--skip-git-repo-check', '--json',
                           '-c', 'model_reasoning_effort="medium"', '-c', 'features.shell_tool=false',
                           '-c', 'features.multi_agent=false', '-c', 'web_search="disabled"',
                           '--output-schema', str(schema), '-o', str(response.resolve()), '-']
                with Path(str(prefix) + '.events.jsonl').open('w') as stdout, Path(str(prefix) + '.stderr.log').open('w') as stderr:
                    proc = subprocess.run(command, input=request, text=True, stdout=stdout, stderr=stderr,
                                          cwd=temp, timeout=300)
            events = []
            for line in Path(str(prefix) + '.events.jsonl').read_text().splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            usage.extend(e.get('usage') for e in events if e.get('type') == 'turn.completed')
            if proc.returncode or not response.exists() or not any(e.get('type') == 'turn.completed' for e in events):
                raise RuntimeError('Judge service failed for ' + name)
            if any(e.get('item', {}).get('type') in ['command_execution', 'mcp_tool_call', 'web_search', 'collab_tool_call'] for e in events):
                raise RuntimeError('Unexpected reviewer tool use')
            result = json.loads(response.read_text())
        except Exception as error:
            base.save(Path(str(prefix) + '.failure.json'), {'error': str(error), 'utc': base.now()})
            stop.set()
            raise
        try:
            base.validate(result, item)
            attempts.append({'number': number, 'valid': True})
            break
        except ValueError as error:
            attempts.append({'number': number, 'valid': False, 'error': str(error)})
            base.save(Path(str(prefix) + '.validation.json'), attempts[-1])
            if retry == 2:
                stop.set()
                raise
            feedback = ('\nMECHANICAL VALIDATION FEEDBACK: ' + str(error) + '\nPrior response: ' +
                        json.dumps(result, ensure_ascii=False) +
                        '\nReassess the supplied input and copy evidence verbatim; preserve the original relevance scale.\n')
    record = {'fingerprint': protocol['fingerprint'], 'result': result,
              'metadata': {'model_requested': protocol['model_requested'], 'reasoning_effort': 'medium',
                           'request_sha256': base.sha(request.encode()), 'abstract_sha256': item['supplied_abstract_sha256'],
                           'original_prompt_sha256': item['original_prompt_sha256'],
                           'elapsed_seconds': time.monotonic() - started, 'attempts': attempts,
                           'usage': usage, 'completed_utc': base.now(), 'origin': 'population_extension'}}
    base.save(out / f'{name}.json', record)
    return name


def run(source, pilot, root, workers, limit):
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'execution.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    items, protocol, reuse = prepare(source, pilot, root, workers)
    done = set()
    for item in items:
        name = base.key(item)
        path = root / 'gpt_reviews' / f'{name}.json'
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        expected = reuse[name]['fingerprint'] if name in reuse else protocol['fingerprint']
        assert record['fingerprint'] == expected
        base.validate(record['result'], item)
        done.add(name)
    pending = [item for item in items if base.key(item) not in done]
    chosen = pending if limit is None else pending[:limit]
    state = {'state': 'running', 'expected': 600, 'completed': len(done), 'pilot_reused': 60,
             'workers': workers, 'remaining': len(pending), 'updated_utc': base.now()}
    base.save(root / 'status.json', state)
    stop, errors = threading.Event(), []
    iterator = iter(chosen)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        active = {}
        def submit_next():
            if stop.is_set():
                return
            item = next(iterator, None)
            if item is not None:
                active[pool.submit(review_one, item, root, protocol, stop)] = base.key(item)
        for _ in range(workers):
            submit_next()
        while active:
            ready, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in ready:
                name = active.pop(future)
                try:
                    accepted = future.result()
                    if accepted:
                        done.add(accepted)
                        print(json.dumps({'completed': len(done), 'pair': accepted, 'remaining': 600 - len(done)}), flush=True)
                except Exception as error:
                    errors.append({'pair': name, 'error': str(error)})
                    stop.set()
            for _ in ready:
                submit_next()
            state.update(completed=len(done), remaining=600 - len(done), updated_utc=base.now())
            base.save(root / 'status.json', state)
    state.update(state='needs_attention' if errors else ('completed' if len(done) == 600 else 'bounded_partial'),
                 completed=len(done), remaining=600 - len(done), errors=errors, updated_utc=base.now())
    base.save(root / 'status.json', state)
    if errors:
        raise RuntimeError(json.dumps(errors))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('docs/feed_matrix_20261031'))
    parser.add_argument('--pilot', type=Path, default=Path('docs/relevance_review_20261105'))
    parser.add_argument('--workers', type=int, default=4, choices=[1, 2, 4])
    parser.add_argument('--limit', type=int)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if args.prepare_only:
        prepare(args.source, args.pilot, args.root, args.workers)
    else:
        run(args.source.resolve(), args.pilot.resolve(), args.root.resolve(), args.workers, args.limit)
