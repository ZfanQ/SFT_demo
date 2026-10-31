import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
review=module('review_summary_factuality')
prepare=module('prepare_factuality_triage')


class FactualityTests(unittest.TestCase):
    def setUp(self):
        self.item={'paper_id':'paper001','candidate_id':'A','candidate':'The trial included 200 adults.',
                   'pages_text':['The trial enrolled 20 adults.','Other results.']}
        self.finding={'status':'contradicted','severity':'major','claim_type':'numbers',
            'candidate_quote':'200 adults','reference_quote':'20 adults','pdf_page':1,'explanation':'Tenfold sample-size overstatement.'}
    def response(self):
        return {'paper_id':'paper001','candidate_id':'A','coverage':'sufficient_text_for_review',
                'coverage_note':'All supplied text reviewed.','verdict':'concerns_identified','findings':[self.finding]}
    def test_exact_evidence_accepted(self):
        review.validate_review(self.response(),self.item)
    def test_wrong_page_rejected(self):
        self.finding['pdf_page']=2
        with self.assertRaises(ValueError):review.validate_review(self.response(),self.item)
    def test_fabricated_quote_rejected(self):
        self.finding['reference_quote']='The trial enrolled 30 adults.'
        with self.assertRaises(ValueError):review.validate_review(self.response(),self.item)
    def test_wrong_paper_rejected(self):
        r=self.response();r['paper_id']='paper002'
        with self.assertRaises(ValueError):review.validate_review(r,self.item)
    def test_missing_support_is_not_definite_error(self):
        self.finding.update(status='unsupported_in_reviewed_material',reference_quote='',pdf_page=0)
        with self.assertRaises(ValueError):review.validate_review(self.response(),self.item)
        self.finding['severity']='uncertain';review.validate_review(self.response(),self.item)
    def test_contradiction_requires_evidence(self):
        self.finding.update(reference_quote='',pdf_page=0)
        with self.assertRaises(ValueError):review.validate_review(self.response(),self.item)
    def test_limited_text_is_not_certification(self):
        r=self.response();r.update(coverage='limited_text',findings=[],verdict='no_issue_identified')
        review.validate_review(r,self.item)
    def test_boolean_page_rejected(self):
        self.finding['pdf_page']=True
        with self.assertRaises(ValueError):review.validate_review(self.response(),self.item)
    def test_selection_is_deterministic_and_controls_disjoint(self):
        flags={f'paper{i:03d}' for i in range(1,21)}
        a=prepare.selection(flags);self.assertEqual(a,prepare.selection(flags))
        self.assertEqual(len(a['calibration_ids']),10);self.assertEqual(len(a['independent_unflagged_controls']),20)
        self.assertFalse(set(a['calibration_ids'])&set(a['independent_unflagged_controls']))
        self.assertFalse(flags&set(a['independent_unflagged_controls']))


if __name__=='__main__':unittest.main()
