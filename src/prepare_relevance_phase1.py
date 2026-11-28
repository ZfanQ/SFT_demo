"""Freeze matched score and evidence targets for the development split."""

import argparse
from collections import Counter
import json
from pathlib import Path

from prepare_relevance_distillation import digest, load


NEUTRAL = 'Assess how relevant the supplied abstract is to the supplied interest. ' \
          'Grades: 0 unrelated, 1 peripheral, 2 relevant, 3 central.'
SCHEMAS = {
    'score': 'Return a single JSON object with an integer grade.',
    'rationale': 'Return a single JSON object with an integer grade, evidence_quote, evidence_role, and reason.',
}
ROLES = [
    {'unrelated'},
    {'background_or_covariate', 'ambiguous'},
    {'secondary_analysis'},
    {'primary_question'},
]


def normalize(text):
    return ' '.join(text.casefold().split())


def teacher_phase(root, phase, teacher, rubric_hash):
    protocol_path = root / 'teacher' / phase / 'protocol.json'
    protocol = load(protocol_path)
    if (protocol['teacher_model'] != teacher['teacher_model']
            or protocol['rubric_sha256'] != rubric_hash
            or protocol['inputs_sha256'] != digest(root / 'inputs' / f'{phase}.json')):
        raise ValueError(f'Unexpected teacher protocol for {phase}')
    expected = {}
    batches = 0
    for name, sha in teacher['source_sha256'].items():
        if not name.startswith(phase + '/'):
            continue
        path = root / 'teacher' / name
        if digest(path) != sha:
            raise ValueError(f'Frozen teacher batch changed: {name}')
        batch = load(path)['result']
        for row in batch['judgments']:
            key = batch['paper_id'], row['interest_id']
            if key in expected:
                raise ValueError('Duplicate frozen judgment')
            expected[key] = {'paper_id': key[0], **row}
        batches += 1
    rows = load(root / 'evaluator' / f'{phase}_reference.json')
    if len(rows) != len(expected) or any(expected.get((r['paper_id'], r['interest_id'])) != r for r in rows):
        raise ValueError(f'Export differs from frozen teacher batches: {phase}')
    return rows, {'batches': batches, 'protocol_sha256': digest(protocol_path),
                  'driver_sha256': protocol['driver_sha256']}


def write_frozen(path, content):
    if path.exists() and path.read_text() != content:
        raise ValueError(f'Existing Phase 1 artifact differs: {path}')
    if not path.exists():
        path.write_text(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = args.run
    config = load(root / 'run_config.json')
    paths = {k: Path(config[k]) for k in ('dataset', 'catalogue', 'split', 'rubric')}
    inputs = {k: digest(p) for k, p in paths.items()}
    if any(sha != load(root / 'inputs/manifest.json')['hashes'][k] for k, sha in inputs.items()):
        raise ValueError('Frozen source changed')
    split_doc = load(paths['split'])
    split = {k: set(v) for k, v in split_doc['split'].items()}
    papers = load(paths['dataset'])['papers']
    catalogue = load(paths['catalogue'])
    texts = {p['paper_id']: p['text'] for p in papers}
    tags = {t['interest_id']: t for t in catalogue}
    if (len(texts) != len(papers) or len({normalize(t) for t in texts.values()}) != len(texts)
            or set.union(*split.values()) != set(texts) or sum(map(len, split.values())) != len(texts)
            or len(tags) != len(catalogue) or any(not t['definition'].strip() for t in catalogue)):
        raise ValueError('Corpus, partitions or interest definitions are inconsistent')
    teacher = load(root / 'evaluator/teacher_freeze.json')
    if teacher['teacher_model'] != config['teacher_model']:
        raise ValueError('Teacher model does not match the run configuration')
    manifest = {'dataset_version': 'phase1-v1', 'teacher': teacher['teacher_model'],
                'input_sha256': inputs, 'input_scope': 'abstract and interest definition',
                'partitions': {k: len(v) for k, v in split.items()}, 'interests': len(tags),
                'exact_duplicate_abstracts': 0, 'historical_duplicate_check': split_doc['duplicate_check'],
                'phases': {}}
    args.out.mkdir(parents=True, exist_ok=True)
    for phase in ('train', 'validation'):
        rows, report = teacher_phase(root, phase, teacher, inputs['rubric'])
        outputs = {arm: [] for arm in SCHEMAS}
        grade_counts, roles = Counter(), Counter()
        pairs = set()
        for row in rows:
            paper, interest = row['paper_id'], row['interest_id']
            grade = row['grade']
            quote = normalize(row['evidence_quote'])
            if (paper not in split[phase] or interest not in tags or (paper, interest) in pairs
                    or type(grade) is not int or grade not in range(4)
                    or (not quote and grade > 0) or (quote and quote not in normalize(texts[paper]))
                    or not row['reason'].strip() or row['evidence_role'] not in ROLES[grade]):
                raise ValueError(f'Invalid judgment in {phase}: {paper}/{interest}')
            pairs.add((paper, interest))
            grade_counts[grade] += 1
            roles[row['evidence_role']] += 1
            shared = {'abstract': texts[paper], 'interest': tags[interest]['label'],
                      'definition': tags[interest]['definition']}
            for arm, schema in SCHEMAS.items():
                fields = ('grade',) if arm == 'score' else ('grade', 'evidence_quote', 'evidence_role', 'reason')
                messages = [{'role': 'system', 'content': NEUTRAL + ' ' + schema},
                            {'role': 'user', 'content': json.dumps(shared, ensure_ascii=False)},
                            {'role': 'assistant', 'content': json.dumps({k: row[k] for k in fields}, ensure_ascii=False)}]
                outputs[arm].append(json.dumps({'paper_id': paper, 'interest_id': interest, 'messages': messages},
                                               ensure_ascii=False))
        hashes = {}
        for arm, lines in outputs.items():
            path = args.out / f'{phase}_{arm}.jsonl'
            write_frozen(path, '\n'.join(lines) + '\n')
            hashes[arm] = digest(path)
        manifest['phases'][phase] = {**report, 'pairs': len(pairs), 'papers': len({p for p, _ in pairs}),
                                     'grades': dict(grade_counts), 'roles': dict(roles), 'sha256': hashes}
    write_frozen(args.out / 'phase1_manifest.json', json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
