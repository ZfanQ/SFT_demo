import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('exporter',Path(__file__).parents[1]/'src/export_factuality_review.py')
exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)


class ExportTests(unittest.TestCase):
    def test_stable_id_does_not_depend_on_human_decision(self):
        row={'paper_id':'paper001','source':'gemma','review_origin':'v3','candidate_quote':'A claim'}
        self.assertEqual(exporter.identifier(row),exporter.identifier({**row,'human_verdict':'confirmed_error'}))

    def test_reexport_preserves_human_fields_and_flags_are_not_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'new';history=Path(directory)/'history'
            def save(path,value):
                path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            save(root/'inputs/manifest.json',{'papers':[{'paper_id':'paper001','pdf_path':'/original/paper001.pdf',
                'historical_hash_matches':{'qwen8b':True},'sources':{'gemma':{'sha256':'hash'}}}]})
            save(root/'inputs/blinding_map.json',{})
            save(root/'inputs/selection.json',{'calibration_ids':['paper001'],'independent_unflagged_controls':[]})
            save(history/'followup_20261020/fulltext_adjudication/manifest.json',{'inputs':{}})
            path=history/'gemma_evaluation_20261023/gpt_scores/evaluations.jsonl'
            save(path,{'paper_id':'paper001','major_factual_error':True,'summary_sha256':'hash'})
            exporter.build(root,history)
            queue=root/'human_review/queue.csv'
            with queue.open() as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['review_status'],'needs_evidence_review')
            self.assertEqual(rows[0]['human_verdict'],'')
            rows[0].update(human_verdict='unresolved',human_reason='Need PDF table.',reviewer='Reviewer 1')
            with queue.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=exporter.FIELDS);writer.writeheader();writer.writerows(rows)
            exporter.build(root,history)
            with queue.open() as stream:revised=list(csv.DictReader(stream))
            self.assertEqual(revised[0]['human_verdict'],'unresolved')
            self.assertEqual(revised[0]['human_reason'],'Need PDF table.')
            self.assertEqual(revised[0]['reviewer'],'Reviewer 1')


if __name__=='__main__':unittest.main()
