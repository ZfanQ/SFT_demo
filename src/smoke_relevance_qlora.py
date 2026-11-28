"""Check evidence-target sizing and one bounded QLoRA optimizer step."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import time


def load_rows(data, phase, arm, manifest):
    path = data / f'{phase}_{arm}.jsonl'
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['phases'][phase]['sha256'][arm]:
        raise ValueError(f'Dataset hash changed: {path}')
    return [json.loads(line) for line in path.read_text().splitlines()]


def encode(tokenizer, row):
    messages = row['messages']
    prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True,
                                           enable_thinking=False)
    if not prompt or tokenizer.eos_token_id is None or '<think>\n\n</think>' not in prompt:
        raise ValueError('Unexpected Qwen chat template or EOS')
    context = tokenizer.encode(prompt, add_special_tokens=False)
    target = tokenizer.encode(messages[-1]['content'], add_special_tokens=False) + [tokenizer.eos_token_id]
    if not context or not target[:-1] or tokenizer.eos_token_id in target[:-1]:
        raise ValueError('Empty context or invalid assistant target')
    return context, target


def statistics(samples):
    lengths = sorted(len(x) + len(y) for x, y in samples)
    return {'max_tokens': lengths[-1], 'p95_tokens': lengths[math.ceil(0.95 * len(lengths)) - 1],
            'assistant_target_tokens': sum(len(y) for _, y in samples), 'total_tokens': sum(lengths)}


class LocalTokenizer:
    """Render the pinned Qwen template and tokenize without importing Torch."""

    def __init__(self, model):
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(model / 'tokenizer.json'))
        config = json.loads((model / 'tokenizer_config.json').read_text())
        eos = config['eos_token']
        self.eos_token_id = self.tokenizer.token_to_id(eos if isinstance(eos, str) else eos['content'])
        self.chat_template = (model / 'chat_template.jinja').read_text()
        environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
        def raise_exception(message):
            raise ValueError(message)
        environment.globals['raise_exception'] = raise_exception
        self.template = environment.from_string(self.chat_template)

    def apply_chat_template(self, messages, tokenize, **options):
        if tokenize:
            raise ValueError('Expected a rendered template')
        return self.template.render(messages=messages, **options)

    def encode(self, text, add_special_tokens=False):
        return self.tokenizer.encode(text, add_special_tokens=add_special_tokens).ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('data', 'model', 'out'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    if args.dry_run:
        tokenizer = LocalTokenizer(args.model)
    else:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True, trust_remote_code=False)
    manifest = json.loads((args.data / 'phase1_manifest.json').read_text())
    tables, metadata = {}, {}
    for phase in ('train', 'validation'):
        metadata[phase] = {}
        expected_ids = None
        for arm in ('score', 'rationale'):
            rows = load_rows(args.data, phase, arm, manifest)
            ids = [(r['paper_id'], r['interest_id'], r['messages'][1]['content'],
                    json.loads(r['messages'][-1]['content'])['grade']) for r in rows]
            if expected_ids is not None and ids != expected_ids:
                raise ValueError(f'Unmatched {phase} pairs or inputs')
            expected_ids = ids
            table = [encode(tokenizer, row) for row in rows]
            tables[phase, arm] = table
            metadata[phase][arm] = statistics(table)
    limit = math.ceil(max(s['max_tokens'] for phase in metadata.values() for s in phase.values()) / 128) * 128
    report = {'token_counts': metadata, 'max_length': limit, 'seed': 20261128,
              'microbatch': 1, 'padding': 'none', 'truncation': 'none', 'thinking': False,
              'chat_template_sha256': hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
              'eos_token_id': tokenizer.eos_token_id, 'loss': 'assistant tokens and EOS only'}
    (args.out / 'dry_run.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)
    if args.dry_run:
        return

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForImageTextToText, BitsAndBytesConfig

    torch.manual_seed(report['seed'])
    config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=False, quantization_config=config,
        device_map={'': 0}, dtype=torch.bfloat16)
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant': False})
    adapter = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0,
                                               target_modules=['q_proj', 'v_proj'], task_type='CAUSAL_LM'))
    trainable = [p for p in adapter.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=1e-4)
    samples = tables['train', 'rationale']
    indices = random.Random(report['seed']).sample(range(len(samples)), 4)
    longest = max(range(len(samples)), key=lambda i: sum(map(len, samples[i])))
    if longest not in indices:
        indices[-1] = longest
    before = [p.detach().clone() for p in trainable]
    losses, tokens = [], 0
    start = time.monotonic()
    adapter.train()
    for index in indices:
        prompt, target = samples[index]
        values = torch.tensor([prompt + target], device='cuda')
        labels = torch.tensor([[-100] * len(prompt) + target], device='cuda')
        with torch.autocast('cuda', dtype=torch.bfloat16):
            loss = adapter(input_ids=values, labels=labels, use_cache=False).loss
        if not torch.isfinite(loss):
            raise RuntimeError('Non-finite training loss')
        (loss / len(indices)).backward()
        losses.append(loss.item())
        tokens += values.numel()
    norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0, error_if_nonfinite=True)
    optimizer.step()
    torch.cuda.synchronize()
    seconds = time.monotonic() - start
    if norm.item() <= 0 or not any(not torch.equal(old, p) for old, p in zip(before, trainable)):
        raise RuntimeError('Adapter parameters did not update')
    path = args.out / 'adapter'
    adapter.save_pretrained(path)
    (args.out / 'step.json').write_text(json.dumps({'losses': losses, 'grad_norm': norm.item(),
        'seconds': seconds, 'tokens': tokens, 'tokens_per_second': tokens / seconds,
        'peak_allocated_mib': torch.cuda.max_memory_allocated() / 2**20,
        'peak_reserved_mib': torch.cuda.max_memory_reserved() / 2**20,
        'adapter_sha256': hashlib.sha256((path / 'adapter_model.safetensors').read_bytes()).hexdigest()}, indent=2))
    unwrapped = adapter.unload()
    restored = PeftModel.from_pretrained(unwrapped, path).eval()
    parsed = 0
    prompts = tables['validation', 'rationale'][:4]
    total_output = 0
    for prompt, _ in prompts:
        values = torch.tensor([prompt], device='cuda')
        with torch.inference_mode():
            output = restored.generate(input_ids=values, attention_mask=torch.ones_like(values),
                                       max_new_tokens=192, do_sample=False, use_cache=True,
                                       pad_token_id=tokenizer.eos_token_id)
        added = output[0, len(prompt):]
        total_output += added.numel()
        try:
            result = json.loads(tokenizer.decode(added, skip_special_tokens=True).strip())
            parsed += (isinstance(result, dict) and type(result.get('grade')) is int
                       and result['grade'] in range(4)
                       and all(isinstance(result.get(key), str) for key in ('evidence_quote', 'evidence_role', 'reason')))
        except (ValueError, TypeError):
            continue
    (args.out / 'reload.json').write_text(json.dumps({'loaded': True, 'parsed': parsed, 'samples': len(prompts),
                                                     'generated_tokens': total_output}, indent=2) + '\n')
    print(f'Adapter reloaded. Rationale schema parsed on {parsed}/{len(prompts)} validation inputs.', flush=True)


if __name__ == '__main__':
    main()
