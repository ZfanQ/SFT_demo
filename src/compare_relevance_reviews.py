#!/usr/bin/env python3
"""Audit blinded judgments and compare each saved configuration on the same pairs."""
import argparse
from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path
import random
import statistics
from zoneinfo import ZoneInfo

from review_relevance_scores import LABELS, PROFILES, key, payload, schema, sha, validate


def write_csv(path, rows, fields=None, preserve=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0])
    previous = {}
    if preserve and path.exists():
        with path.open() as stream:
            previous = {key(row): row for row in csv.DictReader(stream)}
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            row = dict(row)
            for field in preserve:
                row[field] = previous.get(key(row), {}).get(field, '')
            writer.writerow(row)


def metrics(rows):
    n = len(rows)
    return {'pairs': n, 'exact_agreement': sum(r['score_difference'] == 0 for r in rows) / n,
            'within_one': sum(abs(r['score_difference']) <= 1 for r in rows) / n,
            'mean_absolute_difference': statistics.mean(abs(r['score_difference']) for r in rows),
            'two_or_more_difference': sum(abs(r['score_difference']) >= 2 for r in rows),
            'threshold_disagreements': sum(r['threshold_disagreement'] for r in rows),
            'saved_score_higher': sum(r['score_difference'] > 0 for r in rows),
            'saved_score_lower': sum(r['score_difference'] < 0 for r in rows)}


def compare(root, source):
    request_file = root / 'inputs/requests.json'
    inputs = json.loads(request_file.read_text())
    items = {key(item): item for item in inputs}
    selection = json.loads((root / 'inputs/selection.json').read_text())
    selected = {key(item): item for item in selection['selected']}
    assert len(items) == len(selected) == 60 and set(items) == set(selected)
    assert Counter((r['profile_id'], r['sampling_score']) for r in selected.values()) == Counter(
        {(profile, score): 5 for profile in PROFILES for score in range(4)})
    manifest = json.loads((root / 'inputs/manifest.json').read_text())
    for path, digest in manifest['source_files'].items():
        assert sha((source / path).read_bytes()) == digest, 'Original score input changed: ' + path
    folder = root / 'gpt_reviews'
    protocol = json.loads((folder / 'protocol.json').read_text())
    assert protocol['requests_sha256'] == sha(request_file.read_bytes())
    assert protocol['driver_sha256'] == sha(Path(__file__).with_name('review_relevance_scores.py').read_bytes())
    assert protocol['fingerprint'] == sha(json.dumps({k: v for k, v in protocol.items() if k != 'fingerprint'}, sort_keys=True).encode())
    reviews, reviewed_records, used_attempts, rejected_attempts = {}, [], 0, 0
    for name, item in items.items():
        target = folder / f'{name}.json'
        if not target.exists():
            continue
        record = json.loads(target.read_text())
        assert record['fingerprint'] == protocol['fingerprint']
        result = validate(record['result'], item)
        metadata = record['metadata']
        assert metadata['abstract_sha256'] == sha(item['abstract'].encode()) == item['supplied_abstract_sha256']
        assert metadata['original_prompt_sha256'] == sha(item['original_prompt'].encode()) == item['original_prompt_sha256']
        assert metadata['model_requested'] == protocol['model_requested']
        for attempt in metadata['attempts']:
            prefix = folder / f'{name}.attempt{attempt["number"]:02d}'
            events = [json.loads(line) for line in Path(str(prefix) + '.events.jsonl').read_text().splitlines() if line.startswith('{')]
            assert any(e.get('type') == 'turn.completed' for e in events)
            assert not any(e.get('item', {}).get('type') in ['command_execution', 'mcp_tool_call', 'web_search', 'collab_tool_call'] for e in events)
            request = Path(str(prefix) + '.request.txt').read_text()
            supplied = json.loads(request.split('<untrusted_input>\n', 1)[1].split('\n</untrusted_input>', 1)[0])
            assert supplied == payload(item)
            assert set(supplied) == {'paper_id', 'profile_id', 'original_task'}
            used_attempts += 1
            rejected_attempts += not attempt['valid']
        final = folder / f'{name}.attempt{metadata["attempts"][-1]["number"]:02d}'
        assert sha(Path(str(final) + '.request.txt').read_bytes()) == metadata['request_sha256']
        assert json.loads(Path(str(final) + '.response.json').read_text()) == result
        reviews[name] = result
        reviewed_records.append(record)
    saved = json.loads((root / 'inputs/source_scores.json').read_text())
    assert len(saved) == 540 and len({(key(r), r['model_label'], r['parallel']) for r in saved}) == 540
    reconstructed = []
    for label in LABELS:
        for profile in PROFILES:
            for parallel in [2, 4, 8]:
                accepted = json.loads((source / label / f'{profile}_p{parallel}/accepted.json').read_text())
                path = source / label / accepted['attempt'] / 'responses.jsonl'
                for row in map(json.loads, path.read_text().splitlines()):
                    if key(row) in items:
                        original_response = json.loads(row['response']['message']['content'])
                        assert original_response == {field: row[field] for field in ['paper_id', 'profile_id', 'relevance']}
                        reconstructed.append({'paper_id': row['paper_id'], 'profile_id': profile,
                                              'model_label': label, 'parallel': parallel, 'relevance': row['relevance']})
    assert saved == reconstructed, 'Frozen comparison scores differ from original ledgers'
    assert all(set((r['model_label'], r['parallel']) for r in saved if key(r) == name) ==
               {(label, p) for label in LABELS for p in [2, 4, 8]} for name in items)
    baseline = {key(r): r['relevance'] for r in saved if r['model_label'] == 'qwen3_8b' and r['parallel'] == 2}
    assert all(baseline[name] == item['sampling_score'] for name, item in selected.items())
    comparisons = []
    for row in saved:
        if key(row) not in reviews:
            continue
        reference = reviews[key(row)]
        difference = row['relevance'] - reference['relevance']
        comparisons.append({**row, 'gpt_relevance': reference['relevance'], 'score_difference': difference,
                            'threshold_disagreement': (row['relevance'] >= 2) != (reference['relevance'] >= 2),
                            'gpt_scope_ambiguous': reference['scope_ambiguous']})
    groups, per_profile = [], []
    for label in LABELS:
        for parallel in [2, 4, 8]:
            rows = [r for r in comparisons if r['model_label'] == label and r['parallel'] == parallel]
            if not rows:
                continue
            groups.append({'model_label': label, 'parallel': parallel, **metrics(rows)})
            for profile in PROFILES:
                subset = [r for r in rows if r['profile_id'] == profile]
                if subset:
                    per_profile.append({'model_label': label, 'parallel': parallel, 'profile_id': profile, **metrics(subset)})
    queue = []
    for name, reference in reviews.items():
        rows = [r for r in comparisons if key(r) == name]
        largest = max(abs(r['score_difference']) for r in rows)
        flips = sum(r['threshold_disagreement'] for r in rows)
        ambiguous = reference['scope_ambiguous']
        priority = 'high' if largest >= 2 or flips else ('medium' if ambiguous or largest else 'low')
        queue.append({'paper_id': reference['paper_id'], 'profile_id': reference['profile_id'],
                      'priority': priority, 'max_absolute_difference': largest,
                      'configurations_crossing_threshold': flips, 'scope_ambiguous': ambiguous,
                      'agreement_control': False, 'gpt_relevance': reference['relevance'],
                      **{f'{r["model_label"]}_p{r["parallel"]}': r['relevance'] for r in rows},
                      'gpt_evidence_quote': reference['evidence_quote'], 'gpt_rationale': reference['rationale'],
                      'ambiguity_note': reference['ambiguity_note']})
    rng = random.Random(42)
    for profile in PROFILES:
        eligible = sorted((r for r in queue if r['profile_id'] == profile and r['max_absolute_difference'] == 0
                           and not r['scope_ambiguous']), key=lambda r: r['paper_id'])
        for row in rng.sample(eligible, min(2, len(eligible))):
            row['agreement_control'] = True
    queue.sort(key=lambda r: ({'high': 0, 'medium': 1, 'low': 2}[r['priority']],
                              -r['max_absolute_difference'], -r['configurations_crossing_threshold'],
                              r['profile_id'], r['paper_id']))
    if comparisons:
        write_csv(root / 'comparisons.csv', comparisons)
        write_csv(root / 'configuration_summary.csv', groups)
        write_csv(root / 'per_profile_summary.csv', per_profile)
        human_fields = ['human_score', 'human_reason', 'reviewer', 'reviewed_at']
        write_csv(root / 'human_review/priority_queue.csv', queue,
                  list(queue[0]) + human_fields, preserve=human_fields)
    blind_rows = [{'paper_id': item['paper_id'], 'profile_id': item['profile_id'], 'interest': item['interest'],
                   'abstract': item['abstract'], 'scale': protocol['original_scale']}
                  for item in inputs]
    write_csv(root / 'human_review/independent_scores.csv', blind_rows,
              list(blind_rows[0]) + ['human_score', 'human_reason', 'reviewer', 'reviewed_at'],
              preserve=['human_score', 'human_reason', 'reviewer', 'reviewed_at'])
    summary = {'state': 'verified_complete' if len(reviews) == 60 else 'verified_partial',
               'independent_gpt_pairs': len(reviews), 'expected_pairs': 60, 'comparison_rows': len(comparisons),
               'source_score_rows_preserved': 5400, 'review_attempts': used_attempts,
               'rejected_validation_attempts': rejected_attempts,
               'scope_ambiguous_pairs': sum(r['scope_ambiguous'] for r in reviews.values()),
               'high_priority_pairs': sum(r['priority'] == 'high' for r in queue),
               'agreement_controls': sum(r['agreement_control'] for r in queue),
               'independent_human_labels_complete': False,
               'reference_type': 'Independent GPT judgment; human calibration pending',
               'sample_type': 'Profile/8B-p2-score stratified diagnostic sample',
               'aggregates': groups, 'per_profile': per_profile}
    if len(reviews) == 60:
        status = json.loads((root / 'status.json').read_text())
        assert status['state'] == 'completed' and status['completed'] == 60
    if reviewed_records:
        times = [r['metadata']['completed_utc'] for r in reviewed_records]
        summary['first_review_completed_utc'] = min(times)
        summary['last_review_completed_utc'] = max(times)
    (root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (root / 'accepted_reviews.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in reviewed_records))
    report(root, summary, reviews, queue, protocol)
    print(json.dumps({k: v for k, v in summary.items() if k not in ['aggregates', 'per_profile']}, indent=2))


def report(root, summary, reviews, queue, protocol):
    period = 'Experiment started: November 5, 2026.'
    if summary['state'] == 'verified_complete':
        completed = datetime.fromisoformat(summary['last_review_completed_utc']).astimezone(ZoneInfo('Asia/Shanghai'))
        period += f' Completed: {completed:%B} {completed.day}, {completed.year} (Asia/Shanghai).'
    lines = ['# Independent GPT Review of Saved Relevance Scores', '',
             period, '',
             f'GPT independently scored **{summary["independent_gpt_pairs"]}/60 paper–profile pairs** using the original 0–3 scale, '
             f'providing exact abstract evidence and a relevance explanation. The saved model scores were then compared with these judgments, '
             f'producing **{summary["comparison_rows"]} paired comparisons** across three models and three concurrency settings.', '']
    if summary['state'] == 'verified_complete':
        exact = [g['exact_agreement'] for g in summary['aggregates']]
        boundary = [1 - g['threshold_disagreements'] / g['pairs'] for g in summary['aggregates']]
        lines += [f'Across the nine configurations, exact score agreement was **{min(exact):.1%}–{max(exact):.1%}**. '
                  f'Agreement on the score-2 relevance boundary was **{min(boundary):.1%}–{max(boundary):.1%}**. '
                  'The priority queue isolates cases that can change whether an article is considered relevant.', '']
    lines += ['## Design', '',
             '- Three synthetic interest profiles: oncology, cardiovascular medicine and neuroscience.',
             '- Twenty pairs per profile, randomly selected with seed 42: five from each saved Qwen3-8B/p2 score stratum. This balances the diagnostic sample across the scale.',
             '- Each reviewer session receives the original task and abstract. Model names, prior scores, concurrency and sampling labels are withheld. Sessions run in isolated temporary directories with tools and browsing disabled.',
             f'- Judge: `{protocol["model_requested"]}`, medium reasoning, one independent session per pair. The original scale is retained; the response adds evidence, rationale and an explicit scope-ambiguity flag.',
             '- Exact quotations, IDs, score types/ranges and provenance are checked before acceptance. Frozen source hashes and complete raw outputs support resumption and audit.', '',
             '## Agreement with the GPT reference', '',
             '| Saved configuration | Concurrency | Pairs | Exact agreement | Within one point | Mean absolute difference | Difference ≥2 | Relevant/not-relevant disagreements |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for g in summary['aggregates']:
        lines.append(f'| {g["model_label"]} | {g["parallel"]} | {g["pairs"]} | {g["exact_agreement"]:.1%} | '
                     f'{g["within_one"]:.1%} | {g["mean_absolute_difference"]:.3f} | {g["two_or_more_difference"]} | {g["threshold_disagreements"]} |')
    lines += ['', 'The relevant/not-relevant boundary is score 2: scores 0–1 versus 2–3. Differences are saved score minus GPT score. '
              'All configurations are compared on the same reviewed pairs.', '',
              '## Cases for human review', '',
              f'The review flagged **{summary["scope_ambiguous_pairs"]} scope-ambiguous pairs** and identified '
              f'**{summary["high_priority_pairs"]} high-priority pairs** with a difference of at least two points or a relevance-boundary disagreement. '
              f'An additional **{summary["agreement_controls"]} agreement controls** were selected from pairs where all saved configurations agree with GPT and the scope is unambiguous.', '',
              'Start with [the independent scoring form](human_review/independent_scores.csv), recording a human score and reason before consulting GPT judgments. '
              'Then use [the priority queue](human_review/priority_queue.csv) to inspect disagreements, ambiguous scope and agreement controls.', '',
              '| Profile | Paper | Priority | GPT score | Largest score difference | Configurations crossing threshold | Scope ambiguous |',
              '| --- | --- | --- | ---: | ---: | ---: | --- |']
    for row in queue:
        if row['priority'] == 'high' or row['scope_ambiguous'] or row['agreement_control']:
            lines.append(f'| {row["profile_id"]} | {row["paper_id"]} | {row["priority"]} | {row["gpt_relevance"]} | '
                         f'{row["max_absolute_difference"]} | {row["configurations_crossing_threshold"]} | {row["scope_ambiguous"]} |')
    lines += ['', '## Interpretation and next step', '',
              'The results measure agreement with an independent GPT reference on a deliberately score-balanced sample. '
              'Each pair has one accepted GPT judgment. Agreement percentages describe this balanced cohort. '
              'Human labels are the next step for measuring scoring accuracy. '
              'Profile scope remains the original coarse definition, so ambiguous boundaries are documented for later rubric refinement.', '',
              'Review the priority cases and agreement controls, reconcile profile boundaries, and record human judgments. '
              'Any refined scale or profile should create a new evaluation version, preserving the original 5,400 model scores.', '',
              'Detailed records: [configuration summary](configuration_summary.csv), [per-profile metrics](per_profile_summary.csv), '
              '[all paired comparisons](comparisons.csv), `inputs/selection.json`, and `gpt_reviews/protocol.json`.']
    (root / 'report_en.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--source', type=Path, default=Path('docs/feed_matrix_20261031'))
    args = parser.parse_args()
    compare(args.root, args.source)
