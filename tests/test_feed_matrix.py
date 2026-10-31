import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('feed_matrix',Path(__file__).parents[1]/'tools/benchmark_feed_matrix.py')
matrix=importlib.util.module_from_spec(spec);spec.loader.exec_module(matrix)
analysis_spec=importlib.util.spec_from_file_location('feed_analysis',Path(__file__).parents[1]/'tools/analyze_feed_matrix.py')
analysis=importlib.util.module_from_spec(analysis_spec);analysis_spec.loader.exec_module(analysis)
direct_spec=importlib.util.spec_from_file_location('feed_direct',Path(__file__).parents[1]/'tools/benchmark_feed_matrix_llamacpp.py')
direct=importlib.util.module_from_spec(direct_spec);direct_spec.loader.exec_module(direct)
gemma_spec=importlib.util.spec_from_file_location('feed_gemma',Path(__file__).parents[1]/'tools/benchmark_feed_matrix_gemma.py')
gemma=importlib.util.module_from_spec(gemma_spec);gemma_spec.loader.exec_module(gemma)


class FeedMatrixTests(unittest.TestCase):
    def response(self, score=2, **extra):
        return {'message':{'content':json.dumps({'paper_id':'paper001','profile_id':'oncology','relevance':score})},
                'done':True,'done_reason':'stop','prompt_eval_count':500,**extra}

    def test_valid_score(self):
        self.assertEqual(matrix.validate(self.response(),{'paper_id':'paper001','profile_id':'oncology'})['relevance'],2)

    def test_wrong_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            matrix.validate(self.response(),{'paper_id':'paper001','profile_id':'neuroscience'})

    def test_boolean_score_is_rejected(self):
        with self.assertRaises(ValueError):
            matrix.validate(self.response(True),{'paper_id':'paper001','profile_id':'oncology'})

    def test_truncation_and_exhausted_budget_are_rejected(self):
        for response in [self.response(done_reason='length'),self.response(prompt_eval_count=4000)]:
            with self.assertRaises(ValueError):
                matrix.validate(response,{'paper_id':'paper001','profile_id':'oncology'})

    def test_frozen_input_changes_reject_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'abstracts';data.mkdir();output=root/'run';output.mkdir()
            for n in range(1,201):(data/f'paper{n:03d}.txt').write_text(f'Abstract {n}')
            with patch.object(matrix,'ABSTRACTS',data):
                first=matrix.prepare(output)
                self.assertEqual(len(first['inputs']),600)
                self.assertEqual(first,matrix.prepare(output))
                (data/'paper001.txt').write_text('Changed after freezing')
                with self.assertRaises(ValueError):matrix.prepare(output)

    def test_tied_ranks_preserve_ties(self):
        self.assertEqual(analysis.average_ranks([3,0,3,1]),[3.5,1.0,3.5,2.0])
        self.assertAlmostEqual(analysis.spearman([3,0,3,1],[3,0,3,1]),1.0)
        self.assertIsNone(analysis.spearman([1,1,1],[0,1,2]))

    def test_percentile_interpolates(self):
        self.assertEqual(analysis.percentile([1,2,3,4],.5),2.5)

    def test_engine_overlap_is_measured_after_warmup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'server.log'
            p.write_text('llama_context: n_seq_max = 2\n'
                         'slot launch_slot_: id 0 | task 1 | processing task\n'
                         'slot release: id 0 | task 1 | stop processing\n'
                         'slot launch_slot_: id 0 | task 2 | processing task\n'
                         'slot launch_slot_: id 1 | task 3 | processing task\n'
                         'slot release: id 0 | task 2 | stop processing\n'
                         'slot release: id 1 | task 3 | stop processing\n')
            self.assertEqual(analysis.engine_evidence(p,1),{'configured_sequences':2,'observed_measured_slot_peak':2,
                                                          'measured_task_launches':2,'all_measured_slots_released':True})

    def test_direct_backend_selects_cuda_plugin(self):
        env=direct.cuda_environment()
        self.assertEqual(env['GGML_BACKEND_PATH'],'/data/SFT_demo/.tools/ollama/lib/ollama/cuda_v13/libggml-cuda.so')
        self.assertTrue(env['LD_LIBRARY_PATH'].startswith('/data/SFT_demo/.tools/ollama/lib/ollama:'))

    def test_context_parser_handles_both_backend_log_versions(self):
        self.assertEqual(direct.context_per_sequence('llama_context: n_ctx_seq = 4096'),4096)
        self.assertEqual(direct.context_per_sequence('llama_context: n_ctx_per_seq = 4096'),4096)
        self.assertEqual(direct.context_per_sequence('llama_context: n_ctx_seq = 8192'),8192)
        self.assertIsNone(direct.context_per_sequence('unrelated log line'))

    def test_gemma_adapter_preserves_raw_and_rejects_truncation(self):
        raw={'choices':[{'message':{'content':self.response()['message']['content']},'finish_reason':'length'}],
             'usage':{'prompt_tokens':501,'completion_tokens':96}}
        with patch.object(gemma.direct,'native',return_value=raw):
            normalized=gemma.generate('Frozen user input')
        self.assertIs(normalized['native_llamacpp_response'],raw)
        self.assertEqual(normalized['prompt_eval_count'],501)
        self.assertIsNone(normalized['eval_duration'])
        with self.assertRaises(ValueError):
            matrix.validate(normalized,{'paper_id':'paper001','profile_id':'oncology'})

    def test_gemma_renderer_rejects_dropped_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(gemma.direct,'native',side_effect=[{'prompt':'Input was dropped'},{'tokens':[1,2]}]):
                with self.assertRaises(RuntimeError):
                    gemma.verify_rendering(Path(tmp),[{'paper_id':'paper001','prompt':'Frozen user input'}])


if __name__=='__main__':unittest.main()
