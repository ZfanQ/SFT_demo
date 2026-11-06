# Main Idea Summary

## Goal

Compare an **original instruction model** and its **fine-tuned version** on the **same held-out test set**, using the same source texts, task instructions, reference summaries, and evaluator.

The two initial goals are to establish **zero-shot summarization baselines** and test whether **fine-tuning on stronger-model-generated or improved summaries** helps smaller models. “Original” means before our project-specific fine-tuning, not a pretrained Base checkpoint without instruction tuning.

Before collecting data, confirm whether the initial task is **individual-paper summarization** or **a combined summary of several papers in a feed**. Use one fixed task definition, input scope, target audience, and output length for the main comparison.

## Potential Baseline Models

Use the following open-weight instruction models as initial zero-shot candidates. Model selection for fine-tuning will follow development-set evaluation and a memory-feasibility pilot.

| Model | Role |
| --- | --- |
| [**Qwen3-8B**](https://huggingface.co/Qwen/Qwen3-8B) | Primary baseline and initial fine-tuning candidate |
| [**Qwen3-14B**](https://huggingface.co/Qwen/Qwen3-14B) | Larger Qwen baseline to examine the effect of model scale |
| [**Gemma 3 12B IT**](https://huggingface.co/google/gemma-3-12b-it) | Cross-family baseline in a broadly similar size range; use text input only |
| [**Llama 3.1 8B Instruct**](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) | Llama-family baseline at a similar size to Qwen3-8B |

Plan around **24 GB of available GPU memory**. Evaluate models sequentially, using quantized inference where necessary. Start with a small **QLoRA pilot on Qwen3-8B**; larger models may remain inference-only baselines if training exceeds the allocation. A 3–4B model is a fallback if the required input length makes 8B training impractical.

QLoRA combines 4-bit model weights with trainable LoRA adapters to reduce memory requirements ([Hugging Face PEFT documentation](https://huggingface.co/docs/peft/en/developer_guides/quantization)). Feasibility must be measured at the intended sequence length and batch size; loading a model does not establish training feasibility.

Use each model's official chat template with equivalent task instructions. Fix reasoning mode in advance; use non-thinking mode for Qwen3 in the main experiment. Match quantization, precision, and generation settings within each original/fine-tuned pair, and disclose differences across model families.

## Metrics

Full definitions, GPT prompts, and missing-value rules are documented in [rubric.md](rubric.md).

### Automatic metrics

| Metric | What it measures |
| --- | --- |
| **ROUGE-1** | Unigram overlap with the reference summary |
| **ROUGE-2** | Bigram overlap with the reference summary |
| **ROUGE-L** | Longest common subsequence overlap, preserving order without requiring consecutive matches |
| **BERTScore** | Contextual token-embedding similarity to the reference summary |

Report **F1** consistently. Use the same references for all student models and record their provenance. If references are teacher-generated, these scores measure similarity to teacher references, not factual correctness. Do not compare a teacher's self-reference score with student scores. Report N/A when suitable references are unavailable.

### LLM-judge rubric

Score each dimension independently from **1 (poor) to 5 (excellent)** using a fixed GPT evaluator.

| Dimension | Question |
| --- | --- |
| **Coherence** | Is the summary logically organized and easy to follow? |
| **Consistency** | Are the claims supported by the supplied source text? |
| **Fluency** | Is the writing grammatically correct and natural? |
| **Relevance** | Does it include important information and avoid irrelevant details? |
| **Conciseness** | Is it free of unnecessary repetition or elaboration? |

### Factual-error assessment

Following the error categories in Wang et al. (2025), also use GPT to identify **hallucination, particulars, predicate, and entity errors**, with the problematic claim and source evidence. Definitions are in [rubric.md](rubric.md).

This replaces the paper's human factual assessment with **GPT-based annotation**. Report GPT-detected error rates, not human-validated accuracy. Agreement with human judgment has not yet been established.

## Evaluation Protocol

1. **Fix the task and data splits.** Separate training, development, and held-out test data before fine-tuning. Keep duplicate paper versions together; for feed summaries, avoid sharing constituent papers across splits.
2. **Establish zero-shot baselines.** Run the candidate instruction models on development data. Select one or two fine-tuning targets based on quality and measured feasibility.
3. **Prepare training summaries.** Use a fixed stronger model to generate summaries or revise student summaries. The teacher must use the same source scope available to the student. If comparing both strategies, keep them as separately labeled experimental conditions.
4. **Fine-tune and select checkpoints.** Start with the Qwen3-8B QLoRA pilot. Choose prompts, training settings, and checkpoints using development data only.
5. **Evaluate on the frozen test set.** Run original and fine-tuned models on identical inputs and compute ROUGE-1/2/L and BERTScore against the same references.
6. **Apply the fixed GPT evaluator.** Blind model identity, score all five quality dimensions, and run a separate factual-error check. Judge only the final summary, using the exact source text supplied during generation.
7. **Report paired changes.** Report each metric separately, alongside valid sample counts and unassessable or failed evaluations. Record model revisions, evaluator version, prompt version, and generation settings.

The teacher and judge are distinct roles; disclose if the same model serves both. No local deployment of the teacher within the 24 GB student allocation is assumed.

## Results Tables

Repeat the following tables for each fine-tuned model and training strategy. All cells are placeholders.

### Summary quality

| Configuration | R1 | R2 | RL | BERTScore | Coherence | Consistency | Fluency | Relevance | Conciseness |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Original instruction model | — | — | — | — | — | — | — | — | — |
| Fine-tuned model | — | — | — | — | — | — | — | — | — |
| Δ | — | — | — | — | — | — | — | — | — |

R1/R2/RL denote ROUGE F1 scores. Δ = fine-tuned − original; higher is better for all columns.

### GPT-detected factual errors

| Configuration | Hallucination | Particulars | Predicate | Entity | Any error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original instruction model | — | — | — | — | — |
| Fine-tuned model | — | — | — | — | — |
| Δ (percentage points) | — | — | — | — | — |

Lower error rates are better. Categories can overlap. Use the denominators defined in rubric.md and calculate paired changes on the same assessable examples. Do not combine metrics into a single overall score.

## References

Main experimental design reference:

- Wang, J., et al. (2025). **An Empirical Study of Many-to-Many Summarization with Large Language Models.** ACL 2025. [Paper](https://aclanthology.org/2025.acl-long.555/).

Wang et al. evaluate zero-shot and instruction-tuned models with **ROUGE-1, ROUGE-2, ROUGE-L, BERTScore**, and GPT-4o **1–5 ratings for conciseness, coherence, and relevance**. They separately use human annotators to assess four factual-error categories. Our protocol uses GPT for that assessment as well. Model choices and hardware settings are project adaptations, not a reproduction of their experiment.

Additional rubric reference:

- Fabbri, A. R., et al. (2021). **SummEval: Re-evaluating Summarization Evaluation.** TACL. [Paper](https://aclanthology.org/2021.tacl-1.24/) · [Official repository](https://github.com/Yale-LILY/SummEval).

**Consistency** and **fluency** supplement the three quality dimensions above using the SummEval framework, which also includes coherence and relevance.

Additional metric references:

- Lin, C.-Y. (2004). **ROUGE: A Package for Automatic Evaluation of Summaries.** Text Summarization Branches Out. [Paper](https://aclanthology.org/W04-1013/).
- Zhang, T., Kishore, V., Wu, F., Weinberger, K. Q., & Artzi, Y. (2020). **BERTScore: Evaluating Text Generation with BERT.** ICLR. [Paper](https://openreview.net/forum?id=SkeHuCVFDr).
