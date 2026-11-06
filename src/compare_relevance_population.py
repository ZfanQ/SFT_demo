#!/usr/bin/env python3
"""Audit full-cohort GPT relevance judgments and export the teammate's review tables."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random

import review_relevance_scores as base
from compare_relevance_reviews import metrics, write_csv


def compare(root, source):
    inputs = json.loads((root / 'inputs/requests.json').read_text())
    items = {base.key(item): item for item in inputs}
    assert len(items) == 600
    assert Counter(item['profile_id'] for item in inputs) == {p: 200 for p in base.PROFILES}
    manifest = json.loads((root / 'inputs/manifest.json').read_text())
    for path, digest in manifest['source_files'].items():
        assert base.sha((source / path).read_bytes()) == digest, 'Original source changed: ' + path
    dataset = json.loads((source / 'dataset.json').read_text())
    original_inputs = {base.key(item): item for item in dataset['inputs']}
    papers = {p['paper_id']: p for p in dataset['papers']}
    for name, item in items.items():
        assert item['original_prompt'] == original_inputs[name]['prompt']
        assert item['abstract'] == papers[item['paper_id']]['text']
        assert base.sha(item['abstract'].encode()) == item['supplied_abstract_sha256']
    folder = root / 'gpt_reviews'
    protocol = json.loads((folder / 'protocol.json').read_text())
    pilot = json.loads((root / 'inputs/pilot_protocol.json').read_text())
    reused = json.loads((root / 'inputs/reuse_manifest.json').read_text())
    assert len(reused) == 60 and set(reused) <= set(items)
    assert protocol['instructions'] == pilot['instructions']
    assert protocol['schema'] == pilot['schema'] == base.schema()
    assert protocol['model_requested'] == pilot['model_requested']
    assert protocol['requests_sha256'] == base.sha((root / 'inputs/requests.json').read_bytes())
    assert protocol['driver_sha256'] == base.sha(Path(__file__).with_name('review_relevance_population.py').read_bytes())
    assert protocol['base_driver_sha256'] == base.sha(Path(base.__file__).read_bytes())
    assert protocol['fingerprint'] == base.sha(json.dumps({k: v for k, v in protocol.items() if k != 'fingerprint'}, sort_keys=True).encode())
    assert pilot['fingerprint'] == base.sha(json.dumps({k: v for k, v in pilot.items() if k != 'fingerprint'}, sort_keys=True).encode())
    reviews, records, attempts = {}, [], 0
    for name, item in items.items():
        path = folder / f'{name}.json'
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        expected = reused[name]['fingerprint'] if name in reused else protocol['fingerprint']
        assert record['fingerprint'] == expected
        if name in reused:
            assert base.sha(path.read_bytes()) == reused[name]['result_sha256']
        result = base.validate(record['result'], item)
        metadata = record['metadata']
        assert metadata['model_requested'] == protocol['model_requested']
        assert metadata['abstract_sha256'] == item['supplied_abstract_sha256']
        assert metadata['original_prompt_sha256'] == item['original_prompt_sha256']
        for attempt in metadata['attempts']:
            prefix = folder / f'{name}.attempt{attempt["number"]:02d}'
            raw_request = Path(str(prefix) + '.request.txt').read_text()
            supplied = json.loads(raw_request.split('<untrusted_input>\n', 1)[1].split('\n</untrusted_input>', 1)[0])
            assert supplied == base.payload(item)
            events = [json.loads(line) for line in Path(str(prefix) + '.events.jsonl').read_text().splitlines() if line.startswith('{')]
            assert any(e.get('type') == 'turn.completed' for e in events)
            assert not any(e.get('item', {}).get('type') in ['command_execution', 'mcp_tool_call', 'web_search', 'collab_tool_call'] for e in events)
            attempts += 1
        prefix = folder / f'{name}.attempt{metadata["attempts"][-1]["number"]:02d}'
        assert base.sha(Path(str(prefix) + '.request.txt').read_bytes()) == metadata['request_sha256']
        assert json.loads(Path(str(prefix) + '.response.json').read_text()) == result
        reviews[name] = result
        records.append(record)
    saved = json.loads((root / 'inputs/source_scores.json').read_text())
    assert base.sha((root / 'inputs/source_scores.json').read_bytes()) == protocol['source_scores_sha256']
    assert len(saved) == len({(base.key(r), r['model_label'], r['parallel']) for r in saved}) == 5400
    reconstructed = []
    for label in base.LABELS:
        for profile in base.PROFILES:
            for parallel in [2, 4, 8]:
                accepted = json.loads((source / label / f'{profile}_p{parallel}/accepted.json').read_text())
                ledger = source / label / accepted['attempt'] / 'responses.jsonl'
                for row in map(json.loads, ledger.read_text().splitlines()):
                    assert json.loads(row['response']['message']['content']) == {
                        k: row[k] for k in ['paper_id', 'profile_id', 'relevance']}
                    reconstructed.append({'paper_id': row['paper_id'], 'profile_id': profile,
                                          'model_label': label, 'parallel': parallel, 'relevance': row['relevance']})
    assert saved == reconstructed
    comparisons = []
    by_pair = {name: [] for name in items}
    for row in saved:
        name = base.key(row)
        by_pair[name].append(row)
        if name in reviews:
            ref = reviews[name]
            comparisons.append({**row, 'gpt_relevance': ref['relevance'],
                                'score_difference': row['relevance'] - ref['relevance'],
                                'threshold_disagreement': (row['relevance'] >= 2) != (ref['relevance'] >= 2),
                                'gpt_scope_ambiguous': ref['scope_ambiguous']})
    groups, per_profile = [], []
    for label in base.LABELS:
        for parallel in [2, 4, 8]:
            rows = [r for r in comparisons if r['model_label'] == label and r['parallel'] == parallel]
            if not rows:
                continue
            groups.append({'model_label': label, 'parallel': parallel, **metrics(rows)})
            for profile in base.PROFILES:
                subset = [r for r in rows if r['profile_id'] == profile]
                if subset:
                    per_profile.append({'model_label': label, 'parallel': parallel, 'profile_id': profile, **metrics(subset)})
    queue = []
    for name, item in items.items():
        ref = reviews.get(name)
        rows = by_pair[name]
        largest = max(abs(row['relevance'] - ref['relevance']) for row in rows) if ref else ''
        flips = sum((row['relevance'] >= 2) != (ref['relevance'] >= 2) for row in rows) if ref else ''
        ambiguous = ref['scope_ambiguous'] if ref else ''
        priority = ('high' if largest >= 2 or flips else ('medium' if ambiguous or largest else 'low')) if ref else 'pending'
        queue.append({'paper_id': item['paper_id'], 'profile_id': item['profile_id'], 'priority': priority,
                      'review_status': 'gpt_complete' if ref else 'pending_gpt', 'max_absolute_difference': largest,
                      'configurations_crossing_threshold': flips, 'scope_ambiguous': ambiguous,
                      'agreement_control': False, 'gpt_relevance': ref['relevance'] if ref else '',
                      **{f'{row["model_label"]}_p{row["parallel"]}': row['relevance'] for row in rows},
                      'gpt_evidence_quote': ref['evidence_quote'] if ref else '',
                      'gpt_rationale': ref['rationale'] if ref else '',
                      'ambiguity_note': ref['ambiguity_note'] if ref else ''})
    rng = random.Random(42)
    for profile, count in zip(base.PROFILES, [7, 7, 6]):
        eligible = sorted((r for r in queue if r['profile_id'] == profile and r['priority'] == 'low'), key=lambda r: r['paper_id'])
        for row in rng.sample(eligible, min(count, len(eligible))):
            row['agreement_control'] = True
    queue.sort(key=lambda r: ({'high': 0, 'medium': 1, 'low': 2, 'pending': 3}[r['priority']],
                              -(r['max_absolute_difference'] or 0), -(r['configurations_crossing_threshold'] or 0),
                              r['profile_id'], r['paper_id']))
    human_fields = ['human_score', 'human_reason', 'reviewer', 'reviewed_at']
    write_csv(root / 'human_review/priority_queue.csv', queue, list(queue[0]) + human_fields, preserve=human_fields)
    blind = [{'paper_id': item['paper_id'], 'profile_id': item['profile_id'],
              'interest': item['interest'], 'abstract': item['abstract'], 'scale': protocol['original_scale']} for item in inputs]
    write_csv(root / 'human_review/independent_scores.csv', blind, list(blind[0]) + human_fields, preserve=human_fields)
    overview = []
    queue_map = {base.key(r): r for r in queue}
    for pid in sorted(papers):
        row = {'paper_id': pid, 'abstract': papers[pid]['text']}
        for profile in base.PROFILES:
            q = queue_map[profile + '__' + pid]
            row.update({f'{profile}_gpt_score': q['gpt_relevance'], f'{profile}_priority': q['priority'],
                        f'{profile}_ambiguous': q['scope_ambiguous']})
        overview.append(row)
    write_csv(root / 'paper_overview.csv', overview)
    if comparisons:
        write_csv(root / 'comparisons.csv', comparisons)
        write_csv(root / 'configuration_summary.csv', groups)
        write_csv(root / 'per_profile_summary.csv', per_profile)
    status = json.loads((root / 'status.json').read_text()) if (root / 'status.json').exists() else {}
    complete = len(reviews) == 600 and status.get('state') == 'completed'
    summary = {'state': 'verified_complete' if complete else 'verified_partial', 'papers': 200,
               'gpt_pairs': len(reviews), 'expected_pairs': 600, 'pilot_reused': len(set(reviews) & set(reused)),
               'new_pairs': len(set(reviews) - set(reused)), 'comparison_rows': len(comparisons),
               'accepted_review_attempts': attempts, 'high_priority_pairs': sum(r['priority'] == 'high' for r in queue),
               'scope_ambiguous_pairs': sum(bool(r['scope_ambiguous']) for r in reviews.values()),
               'agreement_controls': sum(r['agreement_control'] for r in queue),
               'human_calibration': 'Teammate review pending', 'aggregates': groups, 'per_profile': per_profile,
               'gpt_score_distributions': {p: dict(Counter(r['relevance'] for r in reviews.values() if r['profile_id'] == p)) for p in base.PROFILES}}
    base.save(root / 'summary.json', summary)
    (root / 'accepted_reviews.jsonl').write_text(''.join(json.dumps(record, ensure_ascii=False) + '\n' for record in records))
    report(root, summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ['aggregates', 'per_profile']}, indent=2))


def report(root, summary):
    lines = ['# Full-Cohort Independent Relevance Review', '', 'Run started: November 6, 2026 (Asia/Shanghai).', '',
             f'The review covers **{summary["gpt_pairs"]}/600 paper/profile pairs** from all 200 papers and three original interest profiles. '
             f'It reuses **{summary["pilot_reused"]} unchanged pilot judgments** and adds **{summary["new_pairs"]} new judgments**, '
             f'producing **{summary["comparison_rows"]} comparisons** with the nine saved model/concurrency configurations.', '',
             '## Method', '',
             'The original 0–3 scale, interest profiles, abstracts, model identifier and reviewer instructions are retained. '
             'Each pair receives an isolated GPT session with prior model scores, model identities and concurrency hidden. '
             'Four independent sessions run concurrently; schema, quotation and input hashes are checked before acceptance. '
             'The imported pilot judgments keep their original bytes and provenance. Original model scores remain fixed.', '',
             '## Agreement with the GPT reference', '',
             '| Configuration | Concurrency | Reviewed pairs | Exact agreement | Within one point | Mean absolute difference | Difference ≥2 | Score-2 boundary disagreements |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in summary['aggregates']:
        lines.append(f'| {row["model_label"]} | {row["parallel"]} | {row["pairs"]} | {row["exact_agreement"]:.1%} | '
                     f'{row["within_one"]:.1%} | {row["mean_absolute_difference"]:.3f} | {row["two_or_more_difference"]} | {row["threshold_disagreements"]} |')
    lines += ['', '## Teammate review files', '',
              '- [All 200 papers](paper_overview.csv): one row per paper, with the three GPT scores and priority flags.',
              '- [Independent human scoring form](human_review/independent_scores.csv): all 600 original tasks, with blank human-score fields.',
              '- [Prioritized comparison queue](human_review/priority_queue.csv): GPT evidence, all saved model scores and editable human decisions.',
              '- [Detailed paired comparisons](comparisons.csv) and [per-profile metrics](per_profile_summary.csv).', '',
              f'The current queue has **{summary["high_priority_pairs"]} high-priority pairs**, '
              f'**{summary["scope_ambiguous_pairs"]} scope-ambiguous pairs**, and **{summary["agreement_controls"]} agreement controls**. '
              'High priority marks a score difference of at least two points or a disagreement across the score-2 relevance boundary. '
              'Human reviewers can begin with the independent form, then reconcile priority cases and controls against GPT evidence.', '',
              '## Interpretation and continuation', '',
              'These tables measure agreement with the independent GPT reference across the full frozen collection. '
              'The collection has its original profile/topic distribution; compare per-profile results when interpreting changes from the score-balanced pilot. '
              'The teammate supplies human calibration and resolves scope boundaries. Any refined scale or profile starts a new version.', '',
              'Partial runs identify pending GPT pairs in the overview and queue. Accepted judgments resume without regeneration. '
              'Service or quota failures stop new submissions while preserving completed and in-flight results. '
              'Publication remains in the experimental repository until credibility review and user confirmation.']
    (root / 'report_en.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--source', type=Path, default=Path('docs/feed_matrix_20261031'))
    args = p.parse_args()
    compare(args.root, args.source)
