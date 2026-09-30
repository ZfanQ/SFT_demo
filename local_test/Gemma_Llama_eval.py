#!/usr/bin/env python3
"""Evaluate Gemma 4 12B IT and Llama 3.1 8B Instruct on five PDFs using CUDA.

Keep qwen_eval.py beside this file: PDF extraction, prompts and metric conventions
are shared with that baseline. No Ollama server is required.
"""
from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import re
import sys
import time

import qwen_eval as base

ROOT = Path(__file__).resolve().parent
MODELS = {
    'gemma': ('Gemma 4 12B IT', 'google/gemma-4-12B-it'),
    'llama': ('Llama 3.1 8B Instruct', 'meta-llama/Llama-3.1-8B-Instruct'),
}
SCORES = ('rouge1_f1', 'rouge2_f1', 'rougeL_f1', 'bertscore_f1')
PACKAGES = ('torch', 'transformers', 'accelerate', 'huggingface-hub',
            'tokenizers', 'pymupdf', 'pymupdf4llm', 'rouge-score', 'bert-score')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', nargs='?', default='all',
                        choices=('all', 'generate', 'evaluate', 'export'))
    parser.add_argument('--data-dir', type=Path, default=ROOT)
    parser.add_argument('--reference-dir', type=Path)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/gemma_llama')
    parser.add_argument('--models', nargs='+', choices=tuple(MODELS), default=list(MODELS))
    for key, (_, repository) in MODELS.items():
        parser.add_argument(f'--{key}-model', default=repository)
        parser.add_argument(f'--{key}-revision', default='main')
    parser.add_argument('--device', default='cuda:0', help='CUDA device; CPU fallback is disabled.')
    parser.add_argument('--dtype', choices=('bfloat16', 'float16'), default='bfloat16')
    parser.add_argument('--quantization', choices=('none', 'nf4'), default='none',
                        help='Use nf4 for bitsandbytes 4-bit weights on a 24 GB GPU; dtype sets compute precision.')
    parser.add_argument('--load-in-4bit', dest='quantization', action='store_const', const='nf4',
                        help='Alias for --quantization nf4.')
    parser.add_argument('--attn-implementation', choices=('sdpa', 'flash_attention_2'), default='sdpa')
    parser.add_argument('--context-cap', type=int, default=40960)
    parser.add_argument('--context-margin', type=int, default=256)
    parser.add_argument('--num-predict', '--max-new-tokens', dest='num_predict', type=int, default=768)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--length-tolerance', type=float, default=.10)
    args = parser.parse_args(argv)
    if not re.fullmatch(r'cuda:\d+', args.device):
        parser.error('--device must be cuda:N, for example cuda:0')
    if args.num_predict < 1 or args.context_margin < 32:
        parser.error('Require num-predict >= 1 and context-margin >= 32')
    if args.context_cap <= args.num_predict + args.context_margin:
        parser.error('context-cap must leave room for the paper and prompt')
    if not 0 <= args.length_tolerance <= 1:
        parser.error('length-tolerance must be in [0, 1]')
    args.models = list(dict.fromkeys(args.models))
    args.output_dir = args.output_dir.resolve()
    return args


def cuda_setup(args):
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable. Install a CUDA-enabled PyTorch build and check nvidia-smi.')
    device = torch.device(args.device)
    torch.cuda.set_device(device)
    if args.dtype == 'bfloat16' and not torch.cuda.is_bf16_supported():
        raise RuntimeError('This GPU does not support BF16; use --dtype float16.')
    props = torch.cuda.get_device_properties(device)
    return {'device': str(device), 'name': props.name, 'vram_bytes': props.total_memory,
            'cuda_version': torch.version.cuda, 'python': sys.version, 'platform': platform.platform()}


def release_cuda():
    import torch
    gc.collect()
    torch.cuda.empty_cache()


def cell(value):
    return str(value).replace('|', '/').replace('\n', ' ')


def model_label(label, state):
    settings = state['experiment']['settings']
    if settings.get('quantization', 'none') == 'nf4':
        return label + ' (4-bit NF4)'
    return label


def persist(state, output):
    state['updated_at'] = base.now()
    base.save_json(output / 'run_state.json', state)
    lines = ['# Gemma / Llama paper summarization results', '',
             'R1/R2/RL = ROUGE-1/2/L F1. BERTScore = F1. All scores are on a 0–1 scale.',
             'The mean is reported only when all five papers have been scored for that model.', '',
             '| Model | Scored | R1 | R2 | RL | BERTScore |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for key, (label, _) in MODELS.items():
        label = model_label(label, state)
        rows = state['rows'][key]
        scored = [r for r in rows if r['status'] == 'scored']
        values = [f'{sum(r[m] for r in scored) / 5:.4f}' for m in SCORES] if len(scored) == 5 else ['N/A'] * 4
        lines.append('| ' + ' | '.join([label, f'{len(scored)}/5', *values]) + ' |')
    lines += ['', '## Per-paper scores', '',
              '| Model | Paper | R1 | R2 | RL | BERTScore | Words / target | Status |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for key, (label, _) in MODELS.items():
        label = model_label(label, state)
        for row in state['rows'][key]:
            values = [f'{row[m]:.4f}' for m in SCORES] if row['status'] == 'scored' else ['N/A'] * 4
            words = f"{row.get('generated_words', '—')} / {row['target_words']}"
            lines.append('| ' + ' | '.join([label, row['paper_id'], *values, words, row['status']]) + ' |')
            if row.get('prediction'):
                base.atomic_text(output / 'summaries' / key / f"{row['paper_id']}_{key}.txt", row['prediction'] + '\n')
    lines += ['', '## Protocol', '',
              '- Full-text extraction and English summary prompts are imported from `qwen_eval.py`.',
              '- Only the reference word count enters the prompt; reference text is used only for scoring.',
              '- Greedy decoding, thinking disabled for Gemma, one paper at a time; no input truncation.',
              '- Weight quantization is recorded below and in model labels; BERTScore is not quantized.',
              '- ROUGE uses stemming; BERTScore uses roberta-large layer 17, no IDF or baseline rescaling.',
              '- BERTScore runs on CUDA with batch size 1; inputs exceeding its tokenizer limit fail explicitly.',
              '- References are teacher-generated; their model/version is unknown.',
              '- This run uses Hugging Face weights; the existing quantized Ollama Qwen run used a different runtime.',
              '', '## Run configuration', '', '```json',
              json.dumps(state['experiment']['settings'], indent=2), '```', '',
              'Model identities, versions, input hashes, raw responses and errors are retained in `run_state.json` and `raw/`.']
    failures = [(key, r) for key in MODELS for r in state['rows'][key] if r.get('error')]
    if failures:
        lines += ['', '## Incomplete / failed items', '']
        lines += [f"- {key} / {r['paper_id']}: {cell(r['error'])}" for key, r in failures]
    base.atomic_text(output / 'README.md', '\n'.join(lines) + '\n')


def initialize(args):
    pairs = base.discover(args.data_dir, args.reference_dir)
    settings = {k: v for k, v in vars(args).items()
                if k not in ('stage', 'models', 'output_dir', 'data_dir', 'reference_dir')}
    packages = list(PACKAGES)
    if args.quantization == 'nf4':
        try:
            importlib.metadata.version('bitsandbytes')
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError('4-bit mode requires bitsandbytes. Run: python -m pip install -U bitsandbytes') from exc
        packages.append('bitsandbytes')
        settings['quantization_details'] = {
            'backend': 'bitsandbytes', 'weight_format': 'nf4', 'double_quantization': True,
            'compute_dtype': args.dtype, 'unquantized_modules_dtype': args.dtype,
            'note': 'Supported Linear layers are quantized; embeddings and excluded layers keep floating-point weights.'}
    experiment = {
        'settings': settings,
        'inputs': [{k: p[k] for k in ('paper_id', 'pdf_sha256', 'reference_sha256', 'target_words')} for p in pairs],
        'system_prompt': base.SYSTEM, 'user_prompt': base.USER, 'extraction': base.EXTRACTION,
        'metrics': dict(base.METRIC_CONFIG, device=args.device),
        'versions': {p: importlib.metadata.version(p) for p in packages},
        'implementation_sha256': base.file_hash(__file__),
        'qwen_implementation_sha256': base.file_hash(base.__file__),
    }
    fingerprint = base.digest(experiment)
    path = args.output_dir / 'run_state.json'
    if path.exists():
        state = base.read_json(path)
        if state['fingerprint'] != fingerprint:
            raise ValueError('Inputs, code, settings or package versions changed. Use a new --output-dir to preserve the previous run.')
        # Refresh paths when an otherwise identical experiment was moved.
        for rows in state['rows'].values():
            for row, pair in zip(rows, pairs):
                row.update(pair)
    else:
        if args.stage == 'evaluate':
            raise ValueError('No saved run. Run generate or all first.')
        state = {'created_at': base.now(), 'fingerprint': fingerprint, 'experiment': experiment,
                 'model_identities': {}, 'rows': {key: [dict(p, status='pending') for p in pairs] for key in MODELS}}
    return state


def extract_sources(state, args):
    # Extract once, then share exactly the same text between the two models.
    for index in range(5):
        try:
            source, meta = base.extract(state['rows']['gemma'][index])
            if meta['errors']:
                raise ValueError('; '.join(meta['errors']))
            for rows in state['rows'].values():
                old = rows[index].get('source_text')
                if old is not None and old != source:
                    raise ValueError('Extracted text changed; use a new --output-dir.')
            for rows in state['rows'].values():
                row = rows[index]
                row.update(source_text=source, extraction=meta)
                if row['status'] in ('pending', 'extraction_failed'):
                    row['status'] = 'extracted'
                    row.pop('error', None)
        except Exception as exc:
            for key in args.models:
                state['rows'][key][index].update(status='extraction_failed', error=f'{type(exc).__name__}: {exc}')
        persist(state, args.output_dir)


def clean_completion(tokenizer, token_ids, eos_ids, max_tokens):
    if not token_ids or token_ids[-1] not in eos_ids or len(token_ids) >= max_tokens:
        raise ValueError('Generation did not finish normally or reached num-predict; not scoring truncated output.')
    # Strip only the final EOS and an optional EMPTY Gemma thought block. Decoding
    # with skip_special_tokens=True alone would leave the literal word "thought".
    text = tokenizer.decode(token_ids[:-1], skip_special_tokens=False,
                            clean_up_tokenization_spaces=False).strip()
    text = re.sub(r'^<\|channel>thought\s*<channel\|>\s*', '', text)
    if not text:
        raise ValueError('Empty summary')
    if re.search(r'<\|[^>]*>|<[^<]*\|>|</?think>', text):
        raise ValueError('Thinking trace or special-token leakage detected; raw output retained.')
    return text


class ModelLoadError(RuntimeError):
    """A shared model setup failure must not be retried once per paper."""


def load_generation_model(key, repository, revision, config, args):
    import torch
    import transformers as hf
    # Quantize during loading rather than first allocating the full BF16 model.
    model_class = (getattr(hf, 'Gemma4UnifiedForConditionalGeneration', None)
                   if key == 'gemma' else hf.AutoModelForCausalLM)
    if model_class is None:
        raise ModelLoadError('Transformers lacks Gemma4Unified support; install a current release (see README).')
    kwargs = {'revision': revision, 'config': config, 'trust_remote_code': False,
              'dtype': getattr(torch, args.dtype), 'device_map': {'': args.device},
              'attn_implementation': args.attn_implementation}
    if args.quantization == 'nf4':
        kwargs['quantization_config'] = hf.BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=getattr(torch, args.dtype))
    base.log(f'LOAD {repository}: quantization={args.quantization}, compute={args.dtype}, {args.device}')
    model = model_class.from_pretrained(repository, **kwargs)
    model.eval()
    if any(p.device.type != 'cuda' for p in model.parameters()):
        raise ModelLoadError('All model weights must be on CUDA; CPU/disk offload is disabled.')
    if args.quantization == 'nf4' and not getattr(model, 'is_loaded_in_4bit', False):
        raise ModelLoadError('Requested NF4 but the model was not loaded in 4-bit mode.')
    base.log(f'LOADED {repository}: model footprint {model.get_memory_footprint() / 1024**3:.2f} GiB')
    return model


def generate_model(key, state, args):
    import torch
    import transformers as hf
    rows = state['rows'][key]
    pending = [r for r in rows if not r.get('prediction') and r['status'] != 'extraction_failed']
    if not pending:
        return
    model = tokenizer = None
    try:
        repository = getattr(args, f'{key}_model')
        revision = getattr(args, f'{key}_revision')
        previous = state['model_identities'].get(key, {})
        # Pin a previously resolved Hub revision on resume, even if main has moved.
        revision = previous.get('resolved_revision') or revision
        config = hf.AutoConfig.from_pretrained(repository, revision=revision, trust_remote_code=False)
        resolved = getattr(config, '_commit_hash', None)
        revision = resolved or revision
        expected = 'gemma4_unified' if key == 'gemma' else 'llama'
        if config.model_type != expected:
            raise ValueError(f'{repository}: expected {expected}, found {config.model_type}')
        tokenizer = hf.AutoTokenizer.from_pretrained(repository, revision=revision, trust_remote_code=False)
        if not tokenizer.chat_template:
            raise ValueError('An instruction-tuned checkpoint with a chat template is required.')
        text_config = config.get_text_config()
        context_limit = min(args.context_cap, text_config.max_position_embeddings)
        identity = {'repository': repository, 'resolved_revision': resolved,
                    'config_sha256': base.digest(config.to_dict()),
                    'tokenizer_sha256': base.digest(tokenizer.backend_tokenizer.to_str()),
                    'chat_template_sha256': base.digest(tokenizer.chat_template),
                    'context_limit': context_limit}
        if previous and previous != identity:
            raise ValueError('Model/tokenizer identity changed; use a new --output-dir.')
        state['model_identities'][key] = identity
        persist(state, args.output_dir)
        for row in pending:
            inputs = output = None
            try:
                request = base.messages(row['source_text'], row['target_words'])
                inputs = tokenizer.apply_chat_template(
                    request, tokenize=True, add_generation_prompt=True, enable_thinking=False,
                    return_dict=True, return_tensors='pt', truncation=False)
                count = inputs['input_ids'].shape[-1]
                row['context'] = {'prompt_tokens': count, 'output_reserve': args.num_predict,
                                  'margin': args.context_margin, 'limit': context_limit}
                if count + args.num_predict + args.context_margin > context_limit:
                    raise ValueError(f'Full prompt ({count}) plus output/margin exceeds {context_limit}; no truncation allowed.')
                raw_path = args.output_dir / 'raw' / key / f"{row['paper_id']}.json"
                generation_key = base.digest({'identity': identity, 'input_ids': inputs['input_ids'].tolist(),
                                              'experiment': state['fingerprint']})
                if raw_path.exists():
                    saved = base.read_json(raw_path)
                    if saved['generation_key'] != generation_key or base.digest(saved['token_ids']) != saved['tokens_sha256']:
                        raise ValueError('Raw generation cache mismatch; choose a new --output-dir.')
                    base.log(f"REUSE {key} {row['paper_id']}")
                else:
                    if model is None:
                        try:
                            model = load_generation_model(key, repository, revision, config, args)
                        except Exception as exc:
                            raise ModelLoadError(f'{type(exc).__name__}: {exc}') from exc
                        quant_config = getattr(model.config, 'quantization_config', None)
                        if hasattr(quant_config, 'to_dict'):
                            quant_config = quant_config.to_dict()
                        state.setdefault('model_runtime', {})[key] = {
                            'quantization': args.quantization,
                            'is_loaded_in_4bit': bool(getattr(model, 'is_loaded_in_4bit', False)),
                            'footprint_bytes': model.get_memory_footprint(),
                            'quantization_config': quant_config}
                        persist(state, args.output_dir)
                    eos = model.generation_config.eos_token_id
                    if eos is None:
                        eos = config.eos_token_id
                    eos_ids = [eos] if isinstance(eos, int) else list(eos or [])
                    if not eos_ids:
                        raise ValueError('Checkpoint has no EOS token configuration.')
                    # Fresh greedy config avoids checkpoint sampling defaults and beam settings.
                    gen_config = hf.GenerationConfig(
                        max_new_tokens=args.num_predict, do_sample=False, num_beams=1,
                        use_cache=True, eos_token_id=eos_ids,
                        pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else eos_ids[0],
                        bos_token_id=tokenizer.bos_token_id)
                    hf.set_seed(args.seed)
                    inputs = inputs.to(args.device)
                    torch.cuda.reset_peak_memory_stats()
                    torch.cuda.synchronize()
                    started = time.monotonic()
                    base.log(f"GENERATE {key} {row['paper_id']}: {count} prompt tokens")
                    with torch.inference_mode():
                        # Avoid allocating [full paper length, vocabulary] prefill logits.
                        output = model.generate(**inputs, generation_config=gen_config, logits_to_keep=1)
                    torch.cuda.synchronize()
                    token_ids = output[0, count:].cpu().tolist()
                    saved = {'generation_key': generation_key, 'token_ids': token_ids,
                             'tokens_sha256': base.digest(token_ids), 'eos_ids': eos_ids,
                             'raw_text': tokenizer.decode(token_ids, skip_special_tokens=False),
                             'wall_seconds': time.monotonic() - started,
                             'peak_cuda_allocated_bytes': torch.cuda.max_memory_allocated(),
                             'generation_config': gen_config.to_dict(), 'created_at': base.now()}
                    # Save the first response before validation; never select a better retry.
                    base.save_json(raw_path, saved)
                    output = inputs = None
                prediction = clean_completion(tokenizer, saved['token_ids'], saved['eos_ids'], args.num_predict)
                words = len(prediction.split())
                row.update(prediction=prediction, prediction_sha256=base.digest(prediction),
                           generated_words=words, output_tokens=len(saved['token_ids']),
                           generation_seconds=saved['wall_seconds'],
                           length_compliant=abs(words - row['target_words']) / row['target_words'] <= args.length_tolerance,
                           format_warnings=[] if len(prediction.split('\n\n')) == 1 else ['Multiple paragraphs retained unchanged.'],
                           status='generated')
                row.pop('error', None)
            except ModelLoadError:
                raise
            except Exception as exc:
                row.update(status='generation_failed', error=f'{type(exc).__name__}: {exc}')
                base.log(f"FAILED {key} {row['paper_id']}: {row['error']}")
            finally:
                # Release per-paper tensors even after OOM; never retain them for the next paper.
                inputs = output = None
            release_cuda()
            persist(state, args.output_dir)
    except Exception as exc:
        for row in pending:
            if not row.get('prediction'):
                row.update(status='generation_failed', error=f'{type(exc).__name__}: {exc}')
        base.log(f'FAILED loading {key}: {type(exc).__name__}: {exc}')
        persist(state, args.output_dir)
    finally:
        del model, tokenizer
        release_cuda()


def evaluate(state, args):
    from bert_score import BERTScorer
    from rouge_score import rouge_scorer
    for key in args.models:
        for row in state['rows'][key]:
            if not row.get('prediction') and not row['status'].endswith('failed'):
                row.update(status='evaluation_failed', error='No validated summary available; run generate first.')
    ready = [(key, r) for key in args.models for r in state['rows'][key]
             if r.get('prediction') and r['status'] in ('generated', 'evaluation_failed')]
    if not ready:
        return
    scorer = None
    try:
        base.log(f'BERTScore: roberta-large, layer 17, {args.device}')
        scorer = BERTScorer(model_type='roberta-large', num_layers=17, lang='en',
                            idf=False, rescale_with_baseline=False, use_fast_tokenizer=False,
                            device=args.device, batch_size=1, nthreads=4)
        identity = {'hash': scorer.hash, 'revision': getattr(scorer._model.config, '_commit_hash', None)}
        if state.get('bertscore_identity', identity) != identity:
            raise ValueError('BERTScore encoder identity changed; use a new --output-dir.')
        state['bertscore_identity'] = identity
        rouge = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
        for key, row in ready:
            try:
                if base.digest(row['prediction']) != row['prediction_sha256']:
                    raise ValueError('Saved prediction integrity check failed.')
                reference = ' '.join(row['reference'].split())
                prediction = ' '.join(row['prediction'].split())
                row['bert_reference_tokens'] = base.check_bert_length(scorer._tokenizer, reference)
                row['bert_prediction_tokens'] = base.check_bert_length(scorer._tokenizer, prediction)
                scores = {name + '_f1': value.fmeasure for name, value in rouge.score(reference, prediction).items()}
                precision, recall, f1 = scorer.score([prediction], [reference], batch_size=1)
                scores.update(bertscore_precision=precision[0].item(), bertscore_recall=recall[0].item(), bertscore_f1=f1[0].item())
                if not all(math.isfinite(v) for v in scores.values()):
                    raise ValueError('Non-finite metric value')
                row.update(scores, status='scored')
                row.pop('error', None)
                base.log(f"SCORED {key} {row['paper_id']}: " + ', '.join(f'{m}={row[m]:.4f}' for m in SCORES))
            except Exception as exc:
                row.update(status='evaluation_failed', error=f'{type(exc).__name__}: {exc}')
                base.log(f"FAILED scoring {key} {row['paper_id']}: {row['error']}")
            persist(state, args.output_dir)
    except Exception as exc:
        for _, row in ready:
            if row['status'] != 'scored':
                row.update(status='evaluation_failed', error=f'{type(exc).__name__}: {exc}')
        base.log(f'FAILED metric setup: {type(exc).__name__}: {exc}')
    finally:
        del scorer
        release_cuda()
        persist(state, args.output_dir)


def main(argv=None):
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Linux/H100 target: prevent two processes from writing the same experiment.
    import fcntl
    with (args.output_dir / '.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.stage == 'export':
            persist(base.read_json(args.output_dir / 'run_state.json'), args.output_dir)
            return 0
        environment = cuda_setup(args)
        state = initialize(args)
        state['environment'] = environment
        persist(state, args.output_dir)
        if args.stage in ('all', 'generate'):
            extract_sources(state, args)
            for key in args.models:
                generate_model(key, state, args)
        if args.stage in ('all', 'evaluate'):
            evaluate(state, args)
        persist(state, args.output_dir)
        success = all((bool(r.get('prediction')) and r['status'] not in ('extraction_failed', 'generation_failed'))
                      if args.stage == 'generate' else r['status'] == 'scored'
                      for key in args.models for r in state['rows'][key])
        base.log(f"{'Complete' if success else 'Incomplete'}. Results: {args.output_dir / 'README.md'}")
        return 0 if success else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        base.log(f'ERROR: {type(exc).__name__}: {exc}')
        sys.exit(1)
