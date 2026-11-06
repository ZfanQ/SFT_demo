import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import review_relevance_population as population


class PopulationTests(unittest.TestCase):
    def test_all_pairs_and_original_pilot_bytes_are_preserved(self):
        source = ROOT / 'experiments/performance/feed_matrix_20261031'
        pilot = ROOT / 'experiments/relevance/relevance_review_20261105'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            items, protocol, reused = population.prepare(source, pilot, root, 4)
            self.assertEqual(len(items), 600)
            self.assertEqual(len(reused), 60)
            self.assertEqual(protocol['instructions'], json.loads((pilot / 'gpt_reviews/protocol.json').read_text())['instructions'])
            for name in reused:
                self.assertEqual((root / 'gpt_reviews' / f'{name}.json').read_bytes(),
                                 (pilot / 'gpt_reviews' / f'{name}.json').read_bytes())
            for profile in population.base.PROFILES:
                self.assertEqual(sum(item['profile_id'] == profile for item in items), 200)
            again = population.prepare(source, pilot, root, 4)
            self.assertEqual(items, again[0])

    def test_service_failure_stops_new_submissions(self):
        items = [{'paper_id': f'paper{i:03d}', 'profile_id': 'oncology'} for i in range(1, 21)]
        calls = []
        def fail(item, root, protocol, stop):
            calls.append(item['paper_id'])
            stop.set()
            raise RuntimeError('service unavailable')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(population, 'prepare', return_value=(items, {'fingerprint': 'test'}, {})), \
                 patch.object(population, 'review_one', side_effect=fail):
                with self.assertRaises(RuntimeError):
                    population.run(root, root, root, 4, None)
            status = json.loads((root / 'status.json').read_text())
            self.assertEqual(status['state'], 'needs_attention')
            self.assertEqual(status['completed'], 0)
            self.assertLessEqual(len(calls), 4)

    def test_worker_limit_is_enforced(self):
        items = [{'paper_id': f'paper{i:03d}', 'profile_id': 'oncology'} for i in range(1, 13)]
        lock = threading.Lock()
        active = peak = 0
        def fake(item, root, protocol, stop):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(.02)
            with lock:
                active -= 1
            return population.base.key(item)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(population, 'prepare', return_value=(items, {'fingerprint': 'test'}, {})), \
                 patch.object(population, 'review_one', side_effect=fake):
                population.run(root, root, root, 4, None)
            self.assertEqual(json.loads((root / 'status.json').read_text())['completed'], 12)
            self.assertLessEqual(peak, 4)
            self.assertGreater(peak, 1)


if __name__ == '__main__':
    unittest.main()
