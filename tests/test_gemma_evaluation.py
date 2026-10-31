import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'tools' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


judge = load('gemma_judge', 'score_gemma_gpt.py')
metric = load('gemma_metric', 'score_gemma_saved_summaries.py')


class GemmaProtocolTests(unittest.TestCase):
    def judgment(self, major=False):
        return {'paper_id': 'paper001', 'scores': {'accuracy': 4 if major else 8,
                'coverage': 8, 'clarity': 9, 'conciseness': 9}, 'major_factual_error': major}

    def test_same_weighted_score(self):
        self.assertEqual(judge.validate(self.judgment(), {'paper_id': 'paper001'}, []), 8.2)

    def test_major_error_caps_overall(self):
        self.assertEqual(judge.validate(self.judgment(True), {'paper_id': 'paper001'}, []), 5.0)

    def test_major_error_requires_low_accuracy(self):
        value = self.judgment(True)
        value['scores']['accuracy'] = 8
        with self.assertRaises(ValueError):
            judge.validate(value, {'paper_id': 'paper001'}, [])

    def test_nonfinite_scores_rejected(self):
        value = self.judgment()
        value['scores']['accuracy'] = float('nan')
        with self.assertRaises(ValueError):
            judge.validate(value, {'paper_id': 'paper001'}, [])

    def test_wrong_paper_rejected(self):
        with self.assertRaises(ValueError):
            judge.validate(self.judgment(), {'paper_id': 'paper002'}, [])

    def test_snapshot_uses_gemma_not_qwen_and_freezes_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'output'
            output.mkdir()
            for folder, prefix, text in [('summary_gemma', 'summary_gemma_paper', 'Gemma candidate'),
                                         ('abstract', 'paper', 'Author reference'),
                                         ('summary_gpt6', 'summary_gpt6_paper', 'GPT reference')]:
                d = root / folder
                d.mkdir()
                for n in range(1, 201):
                    (d / f'{prefix}{n:03d}.txt').write_text(text)
            snapshot = metric.snapshot(root, output)
            entry = snapshot['inputs']['candidate_gemma']['1']
            self.assertEqual((output / entry['snapshot_path']).read_text(), 'Gemma candidate')
            self.assertEqual(set(snapshot['inputs']), {'candidate_gemma', 'author_abstract', 'gpt_reference'})
            self.assertEqual(entry['sha256'], metric.sha(b'Gemma candidate'))

    def test_concurrent_calls_save_each_result_once(self):
        with tempfile.TemporaryDirectory() as directory:
            records = [{'paper_id': f'paper{i:03d}'} for i in range(1, 9)]
            results, by_id = [], {}
            state = {'state': 'running', 'evaluated': 0, 'failed': []}
            with patch.object(judge, 'OUT', Path(directory)), patch.object(judge, 'evaluate', side_effect=lambda r, _: {**r, 'overall': 8.0}), patch.object(judge, 'exports'), patch.object(judge, 'sync'):
                judge.concurrent_scores(records, results, by_id, state, '', 4)
            saved = [json.loads(x) for x in (Path(directory) / 'evaluations.jsonl').read_text().splitlines()]
            self.assertEqual(len(saved), 8)
            self.assertEqual(len({x['paper_id'] for x in saved}), 8)
            self.assertEqual(state['evaluated'], 8)

    def test_quota_stops_new_scheduling_and_preserves_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            records = [{'paper_id': f'paper{i:03d}'} for i in range(1, 9)]
            state = {'state': 'running', 'evaluated': 0, 'failed': []}
            with patch.object(judge, 'OUT', Path(directory)), patch.object(judge, 'evaluate', side_effect=RuntimeError('usage limit reached')) as call, patch.object(judge, 'sync'):
                judge.concurrent_scores(records, [], {}, state, '', 1)
            self.assertEqual(call.call_count, 1)
            self.assertEqual(state['state'], 'blocked')
            self.assertEqual(state['blocker'], 'usage limit reached')


if __name__ == '__main__':
    unittest.main()
