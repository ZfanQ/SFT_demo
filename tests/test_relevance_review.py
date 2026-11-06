import importlib.util
from pathlib import Path
import tempfile
import unittest
import sys
import csv

spec = importlib.util.spec_from_file_location('review', Path(__file__).parents[1] / 'src/review_relevance_scores.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from compare_relevance_reviews import metrics, write_csv


class RelevanceReviewTests(unittest.TestCase):
    def setUp(self):
        self.item = {'paper_id': 'paper001', 'profile_id': 'oncology',
                     'abstract': 'This study examines tumor growth in mice.',
                     'original_prompt': 'Original interest and abstract task.'}
        self.response = {'paper_id': 'paper001', 'profile_id': 'oncology', 'relevance': 3,
                         'evidence_quote': 'tumor growth in mice', 'rationale': 'Direct oncology topic.',
                         'scope_ambiguous': False, 'ambiguity_note': ''}

    def test_exact_evidence_accepted(self):
        self.assertEqual(review.validate(self.response, self.item)['relevance'], 3)

    def test_boolean_or_out_of_range_score_rejected(self):
        for score in [True, -1, 4, 2.0]:
            with self.assertRaises(ValueError):
                review.validate({**self.response, 'relevance': score}, self.item)

    def test_wrong_profile_rejected(self):
        with self.assertRaises(ValueError):
            review.validate({**self.response, 'profile_id': 'neuroscience'}, self.item)

    def test_fabricated_quote_rejected(self):
        with self.assertRaises(ValueError):
            review.validate({**self.response, 'evidence_quote': 'heart failure'}, self.item)

    def test_ambiguity_requires_description(self):
        with self.assertRaises(ValueError):
            review.validate({**self.response, 'scope_ambiguous': True}, self.item)
        review.validate({**self.response, 'scope_ambiguous': True,
                         'ambiguity_note': 'Profile does not specify this disease boundary.'}, self.item)

    def test_reviewer_payload_omits_saved_scores_and_selection_labels(self):
        item = {**self.item, 'model_label': 'hidden', 'parallel': 8, 'relevance': 0, 'sampling_score': 0}
        self.assertEqual(set(review.payload(item)), {'paper_id', 'profile_id', 'original_task'})
        self.assertEqual(review.payload(item)['original_task'], item['original_prompt'])

    def test_selection_balances_each_profile_and_saved_score(self):
        rows = [{'paper_id': f'paper{i:03d}', 'profile_id': profile, 'relevance': score}
                for profile in review.PROFILES for score in range(4)
                for i in range(score * 10 + 1, score * 10 + 11)]
        selected = review.select_pairs(rows)
        self.assertEqual(selected, review.select_pairs(rows))
        self.assertEqual(len({review.key(item) for item in selected}), 60)
        for profile in review.PROFILES:
            for score in range(4):
                self.assertEqual(sum(item['profile_id'] == profile and item['sampling_score'] == score
                                     for item in selected), 5)

    def test_changed_frozen_input_rejects_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'input.json'
            review.freeze(path, {'score': 1})
            review.freeze(path, {'score': 1})
            with self.assertRaises(ValueError):
                review.freeze(path, {'score': 2})

    def test_pairwise_metrics_count_large_and_threshold_disagreements(self):
        result = metrics([{'score_difference': 0, 'threshold_disagreement': False},
                          {'score_difference': -2, 'threshold_disagreement': True},
                          {'score_difference': 1, 'threshold_disagreement': False}])
        self.assertAlmostEqual(result['exact_agreement'], 1 / 3)
        self.assertAlmostEqual(result['within_one'], 2 / 3)
        self.assertEqual(result['mean_absolute_difference'], 1)
        self.assertEqual(result['two_or_more_difference'], 1)
        self.assertEqual(result['threshold_disagreements'], 1)
        self.assertEqual(result['saved_score_higher'], 1)
        self.assertEqual(result['saved_score_lower'], 1)

    def test_export_preserves_human_zero_score_and_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'human.csv'
            rows = [{'paper_id': 'paper001', 'profile_id': 'oncology', 'abstract': 'Frozen abstract'}]
            fields = ['paper_id', 'profile_id', 'abstract', 'human_score', 'human_reason']
            write_csv(path, rows, fields, preserve=['human_score', 'human_reason'])
            with path.open() as stream:
                edited = list(csv.DictReader(stream))
            edited[0].update(human_score='0', human_reason='Outside defined interest.')
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(edited)
            write_csv(path, rows, fields, preserve=['human_score', 'human_reason'])
            with path.open() as stream:
                kept = list(csv.DictReader(stream))
            self.assertEqual(kept[0]['human_score'], '0')
            self.assertEqual(kept[0]['human_reason'], 'Outside defined interest.')


if __name__ == '__main__':
    unittest.main()
