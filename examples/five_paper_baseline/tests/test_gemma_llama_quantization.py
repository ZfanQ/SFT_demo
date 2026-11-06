"""Offline regression checks; no torch/transformers installation or downloads."""
import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import Gemma_Llama_eval as ev


class QuantizationTests(unittest.TestCase):
    def test_cli_default_and_alias(self):
        self.assertEqual(ev.parse_args([]).quantization, 'none')
        self.assertEqual(ev.parse_args(['--quantization', 'nf4']).quantization, 'nf4')
        self.assertEqual(ev.parse_args(['--load-in-4bit']).quantization, 'nf4')

    def test_loader_quantizes_during_load_and_keeps_cuda(self):
        for mode in ('none', 'nf4'):
            with self.subTest(mode=mode):
                model = Mock(is_loaded_in_4bit=mode == 'nf4')
                model.parameters.return_value = [SimpleNamespace(device=SimpleNamespace(type='cuda'))]
                model.get_memory_footprint.return_value = 8 * 1024**3
                loader = Mock()
                loader.from_pretrained.return_value = model
                hf = SimpleNamespace(Gemma4UnifiedForConditionalGeneration=loader,
                                     AutoModelForCausalLM=loader, BitsAndBytesConfig=Mock())
                torch = SimpleNamespace(bfloat16='bf16')
                with patch.dict(sys.modules, torch=torch, transformers=hf), patch.object(ev.base, 'log'):
                    args = ev.parse_args(['--quantization', mode])
                    self.assertIs(ev.load_generation_model('gemma', 'repo', 'commit', object(), args), model)
                kwargs = loader.from_pretrained.call_args.kwargs
                self.assertEqual(kwargs['device_map'], {'': 'cuda:0'})
                self.assertEqual(kwargs['dtype'], 'bf16')
                if mode == 'nf4':
                    hf.BitsAndBytesConfig.assert_called_once_with(
                        load_in_4bit=True, bnb_4bit_quant_type='nf4',
                        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype='bf16')
                    self.assertIs(kwargs['quantization_config'], hf.BitsAndBytesConfig.return_value)
                else:
                    self.assertNotIn('quantization_config', kwargs)
                    hf.BitsAndBytesConfig.assert_not_called()

    def test_setup_failure_is_not_retried_for_each_paper(self):
        ids = SimpleNamespace(shape=(1, 10), tolist=lambda: [[1] * 10])
        tokenizer = SimpleNamespace(chat_template='template',
                                    backend_tokenizer=SimpleNamespace(to_str=lambda: 'tokenizer'),
                                    apply_chat_template=lambda *a, **kw: {'input_ids': ids})
        config = SimpleNamespace(model_type='gemma4_unified', _commit_hash='fixed',
                                 to_dict=lambda: {},
                                 get_text_config=lambda: SimpleNamespace(max_position_embeddings=40960))
        hf = SimpleNamespace(AutoConfig=SimpleNamespace(from_pretrained=lambda *a, **kw: config),
                             AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **kw: tokenizer))
        rows = [dict(paper_id=f'paper_{i:03d}', status='extracted', source_text='paper', target_words=137)
                for i in range(1, 6)]
        state = {'rows': {'gemma': rows}, 'model_identities': {}, 'fingerprint': 'test'}
        with tempfile.TemporaryDirectory() as directory:
            args = ev.parse_args(['--quantization', 'nf4', '--output-dir', directory])
            with patch.dict(sys.modules, torch=SimpleNamespace(), transformers=hf), \
                    patch.object(ev, 'load_generation_model', side_effect=RuntimeError('CUDA OOM')) as load, \
                    patch.object(ev, 'persist'), patch.object(ev, 'release_cuda'), patch.object(ev.base, 'log'):
                ev.generate_model('gemma', state, args)
            load.assert_called_once()
        self.assertTrue(all(r['status'] == 'generation_failed' and 'CUDA OOM' in r['error'] for r in rows))

    def test_reports_label_quantized_results_and_reject_partial_means(self):
        rows = [dict(paper_id=f'paper_{i:03d}', target_words=137, status='scored',
                     **{m: .25 for m in ev.SCORES}) for i in range(1, 6)]
        state = {'experiment': {'settings': {'quantization': 'nf4'}},
                 'rows': {'gemma': copy.deepcopy(rows), 'llama': copy.deepcopy(rows)}}
        state['rows']['llama'][4]['status'] = 'pending'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            ev.persist(state, output)
            text = (output / 'README.md').read_text()
            self.assertIn('| Gemma 4 12B IT (4-bit NF4) | 5/5 | 0.2500', text)
            self.assertIn('| Llama 3.1 8B Instruct (4-bit NF4) | 4/5 | N/A', text)
            self.assertIn('BERTScore is not quantized', text)


if __name__ == '__main__':
    unittest.main()
