#!/usr/bin/env python3
"""Independently verify complete Gemma metric and GPT score exports."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = args.root
    metric = root / 'metrics'
    scores = root / 'gpt_scores'
    assert json.loads((metric / 'status.json').read_text())['state'] == 'completed'
    score_status = json.loads((scores / 'status.json').read_text())
    assert score_status['state'] == 'completed' and score_status['evaluated'] == 200
    assert not score_status['failed']
    rows = [json.loads(x) for x in (metric / 'per_paper.jsonl').read_text().splitlines()]
    assert len(rows) == 400
    assert {(r['reference_type'], r['number']) for r in rows} == {(ref, n) for ref in ['author_abstract', 'gpt_reference'] for n in range(1, 201)}
    conf = json.loads((metric / 'metric_config.json').read_text())
    old_conf = json.loads((root / 'qwen_metric_config.json').read_text())
    compared = [k for k in conf if k not in ['script_sha256', 'input_snapshot_sha256']]
    assert all(conf[k] == old_conf[k] for k in compared), 'Metric configuration differs'
    manifest = json.loads((metric / 'input_manifest.json').read_text())
    old_manifest = json.loads((root / 'results/qwen8b_dual_reference_metrics_20261013T112401Z/input_manifest.json').read_text())
    for ref in ['author_abstract', 'gpt_reference']:
        for n in range(1, 201):
            assert manifest['inputs'][ref][str(n)]['sha256'] == old_manifest['inputs'][ref][str(n)]['sha256']
    for row in rows:
        assert row['model'] == 'google/gemma-4-12B-it'
        n = str(row['number'])
        assert row['candidate_sha256'] == manifest['inputs']['candidate_gemma'][n]['sha256']
        assert row['reference_sha256'] == manifest['inputs'][row['reference_type']][n]['sha256']
        for key in ['rouge1_f1', 'rouge2_f1', 'rougeL_f1', 'bertscore_f1']:
            assert math.isfinite(row[key])
    summary = json.loads((metric / 'summary.json').read_text())
    assert not summary['current_source_changes_since_snapshot']
    matched = {n for n in range(1, 201) if all(r['bertscore_status'] == 'scored_full_text' for r in rows if r['number'] == n)}
    for agg in summary['aggregates']:
        selected = [r for r in rows if r['reference_type'] == agg['reference_type'] and (agg['subset'] == 'all_available' or r['number'] in matched)]
        assert len(selected) == agg['papers']
        for key in ['rouge1_f1', 'rouge2_f1', 'rougeL_f1', 'bertscore_f1']:
            assert math.isclose(statistics.mean(r[key] for r in selected), agg[key], abs_tol=1e-12)
    evaluations = [json.loads(x) for x in (scores / 'evaluations.jsonl').read_text().splitlines()]
    assert len(evaluations) == 200 and {r['paper_id'] for r in evaluations} == {f'paper{i:03d}' for i in range(1, 201)}
    inputs = {x['paper_id']: x for x in json.loads((scores / 'inputs.json').read_text())}
    rubric_hash = sha((scores / 'rubric.md').read_bytes())
    previous = {x['paper_id']: x for x in json.loads((root / 'GPT_eval/inputs.json').read_text())}
    weights = {'accuracy': .5, 'coverage': .25, 'clarity': .15, 'conciseness': .1}
    for row in evaluations:
        pid = row['paper_id']
        assert isinstance(row['major_factual_error'], bool)
        assert 0 < row['summary_words'] <= 250
        assert row['paper_sha256'] == inputs[pid]['paper_sha256'] == previous[pid]['paper_sha256']
        assert row['summary_sha256'] == inputs[pid]['summary_sha256'] == manifest['inputs']['candidate_gemma'][str(int(pid[5:]))]['sha256']
        assert row['rubric_sha256'] == rubric_hash
        assert row['judge_model'] == 'gpt-6.1-sol' and row['reasoning_effort'] == 'medium'
        assert row['evaluation_mode'] == 'scores_only'
        for value in row['scores'].values():
            assert isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 1 <= value <= 10
        overall = sum(row['scores'][k] * v for k, v in weights.items())
        if row['major_factual_error']:
            assert row['scores']['accuracy'] <= 4
            overall = min(overall, 5.0)
        assert row['overall'] == round(overall, 1)
    exported = list(csv.DictReader((scores / 'scores.csv').open()))
    assert len(exported) == 200
    by_id = {r['paper_id']: r for r in evaluations}
    for row in exported:
        expected = by_id[row['paper_id']]
        assert float(row['overall']) == expected['overall']
        assert all(float(row[k]) == expected['scores'][k] for k in weights)
    gpt_summary = {key: statistics.mean((r['overall'] if key == 'overall' else r['scores'][key]) for r in evaluations) for key in ['overall', *weights]}
    report = {'metric_pairs': len(rows), 'gpt_papers': len(evaluations), 'duplicate_ids': False,
              'all_metric_config_keys_match_qwen': compared, 'both_reference_sets_match_qwen_hashes': True,
              'gpt_candidate_and_metric_candidate_hashes_match': True,
              'all_original_pdf_hashes_match_qwen_gpt_evaluation': True,
              'independent_aggregate_recalculation_passed': True, 'matched_untruncated_papers': len(matched),
              'gpt_means': gpt_summary, 'gpt_median': statistics.median(r['overall'] for r in evaluations),
              'gpt_major_flags': [r['paper_id'] for r in evaluations if r['major_factual_error']],
              'artifact_sha256': {str(path.relative_to(root)): sha(path.read_bytes()) for path in
                                 [metric / 'per_paper.jsonl', metric / 'summary.json',
                                  scores / 'evaluations.jsonl', scores / 'scores.csv', scores / 'rubric.md']},
              'warning': 'Scores-only flags are automated judgments, not confirmed error incidence.'}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
