"""Export rationale targets from the original teaching split."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    config = load(args.run / 'run_config.json')
    split_path = Path(config['split'])
    split = {key: set(ids) for key, ids in load(split_path)['split'].items()}
    source_splits = list(split.values())
    if sum(map(len, source_splits)) != len(set.union(*source_splits)):
        raise ValueError('Paper partitions overlap')

    dataset = Path(config['dataset'])
    catalogue = Path(config['catalogue'])
    papers = {row['paper_id']: row for row in load(dataset)['papers']}
    interests = {row['interest_id']: row for row in load(catalogue)}
    rubric = Path(config['rubric'])
    system_prompt = rubric.read_text().split('Illustrative examples', 1)[0].strip()
    system_prompt += '\nReturn a JSON object with grade, evidence_quote, evidence_role, and reason.'
    frozen_inputs = load(args.run / 'inputs/manifest.json')['hashes']
    for name, path in [('dataset', dataset), ('catalogue', catalogue), ('rubric', rubric), ('split', split_path)]:
        if digest(path) != frozen_inputs[name]:
            raise ValueError(f'Frozen source changed: {name}')
    refs = {phase: args.run / 'evaluator' / f'{phase}_reference.json' for phase in ('train', 'validation')}
    coverage = {}
    training_rows = []
    for phase, path in refs.items():
        pairs = set()
        for row in load(path):
            paper_id, interest_id = row['paper_id'], row['interest_id']
            key = paper_id, interest_id
            if paper_id not in split[phase] or key in pairs:
                raise ValueError(f'Unexpected or duplicate {phase} pair')
            paper, interest = papers[paper_id], interests[interest_id]
            evidence = row['evidence_quote']
            if (not evidence.strip() or ' '.join(evidence.split()) not in ' '.join(paper['text'].split())
                    or type(row['grade']) is not int or not 0 <= row['grade'] <= 3
                    or not row['reason'].strip() or not row['evidence_role'].strip()):
                raise ValueError(f'Malformed evidence target for {key}')
            pairs.add(key)
            if phase == 'train':
                data = {'abstract': paper['text'], 'interest': interest['label'], 'definition': interest['definition']}
                if paper.get('title'):
                    data['title'] = paper['title']
                target = {field: row[field] for field in ('grade', 'evidence_quote', 'evidence_role', 'reason')}
                training_rows.append({'paper_id': paper_id, 'interest_id': interest_id, 'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)},
                    {'role': 'assistant', 'content': json.dumps(target, ensure_ascii=False)},
                ]})
        coverage[phase] = {'pairs': len(pairs), 'covered_papers': len({p for p, _ in pairs}),
                           'partition_papers': len(split[phase]), 'covered_interests': len({i for _, i in pairs})}

    if not training_rows:
        raise ValueError('No validated teaching rows')
    args.out.mkdir(parents=True, exist_ok=True)
    output = args.out / 'train_messages.jsonl'
    output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in training_rows))
    grades = Counter(json.loads(row['messages'][-1]['content'])['grade'] for row in training_rows)
    manifest = {'format': 'relevance-rationale-messages-v1', 'coverage': coverage,
                'catalogue_interests': len(interests), 'training_grade_counts': dict(sorted(grades.items())),
                'training_rows_with_titles': sum(bool(papers[row['paper_id']].get('title')) for row in training_rows),
                'source_sha256': {key: digest(path) for key, path in refs.items()},
                'training_export_sha256': digest(output)}
    (args.out / 'coverage.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
