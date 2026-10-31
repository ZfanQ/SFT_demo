import copy
import importlib.util
from pathlib import Path
import unittest
import sys
import tempfile
import fcntl
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("review", Path(__file__).parents[1] / "tools/review_summary_evidence.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
sys.modules["review_summary_evidence"] = m
spec2 = importlib.util.spec_from_file_location("adjudicate", Path(__file__).parents[1] / "tools/adjudicate_summary_evidence.py")
a = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(a)


class EvidenceValidation(unittest.TestCase):
    def setUp(self):
        self.supplied = {"paper001": {"author_abstract": "Treatment did not improve survival.",
                          "candidates": [{"label": "A", "text": "Treatment improved survival."},
                                         {"label": "B", "text": "No survival improvement was observed."}]}}
        self.result = {"papers": [{"paper_id": "paper001", "candidates": [
            {"label": "A", "findings": [{"kind": "abstract_conflict", "severity": "major",
             "candidate_quote": "improved survival", "reference_quote": "did not improve survival",
             "explanation": "Reverses the main outcome."}]}, {"label": "B", "findings": []}]}]}

    def test_valid_quotes(self):
        self.assertEqual(len(m.validate(self.result, self.supplied)), 1)

    def test_fabricated_quote_rejected(self):
        self.result["papers"][0]["candidates"][0]["findings"][0]["reference_quote"] = "significantly improved"
        with self.assertRaisesRegex(ValueError, "evidence"):
            m.validate(self.result, self.supplied)

    def test_noncontiguous_quote_rejected(self):
        self.result["papers"][0]["candidates"][0]["findings"][0]["reference_quote"] = "Treatment survival"
        with self.assertRaises(ValueError):
            m.validate(self.result, self.supplied)

    def test_wrong_or_duplicate_paper_rejected(self):
        self.result["papers"].append(copy.deepcopy(self.result["papers"][0]))
        with self.assertRaises(ValueError):
            m.validate(self.result, self.supplied)

    def test_duplicate_candidate_rejected(self):
        self.result["papers"][0]["candidates"][1]["label"] = "A"
        with self.assertRaises(ValueError):
            m.validate(self.result, self.supplied)

    def test_fulltext_verdict_requires_definite_evidence(self):
        supplied = copy.deepcopy(self.supplied)
        supplied["paper001"]["full_article"] = supplied["paper001"].pop("author_abstract")
        result = copy.deepcopy(self.result)
        for c in result["papers"][0]["candidates"]:
            c["verdict"] = "material_error_identified" if c["label"] == "A" else "no_material_error_identified"
        a.validate(result, supplied)
        result["papers"][0]["candidates"][0]["findings"][0]["severity"] = "uncertain"
        with self.assertRaisesRegex(ValueError, "inconsistency"):
            a.validate(result, supplied)

    def test_fulltext_fabricated_evidence_rejected(self):
        supplied = copy.deepcopy(self.supplied)
        supplied["paper001"]["full_article"] = "An unrelated article with a different result."
        result = copy.deepcopy(self.result)
        for c in result["papers"][0]["candidates"]:
            c["verdict"] = "material_error_identified" if c["label"] == "A" else "no_material_error_identified"
        with self.assertRaisesRegex(ValueError, "Evidence not found"):
            a.validate(result, supplied)

    def test_second_writer_stops_before_loading_sources_or_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            with (Path(directory) / ".run.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                argv = ["adjudicate", "--snapshot", "/nonexistent", "--screening", "/nonexistent",
                        "--output", directory, "--ids", "1"]
                with patch.object(sys, "argv", argv), self.assertRaises(BlockingIOError):
                    a.main()


if __name__ == "__main__":
    unittest.main()
