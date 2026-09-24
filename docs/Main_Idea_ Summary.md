# Main Idea Summary

## Goal

Compare the **base model** and **fine-tuned model** on the **same held-out test set** using the same inputs, prompts, references, and evaluator.


## Potential Baseline Models

Use several open-weight instruction models as baselines before fine-tuning. A reasonable initial set is:

| Model | Role |
| --- | --- |
| **Qwen3-8B** | Primary baseline and likely fine-tuning target |
| **Qwen3-14B** | Larger Qwen baseline to test the effect of model scale |
| **Gemma 3 12B IT** | Comparable model from a different model family |
| **Llama 3.1 8B Instruct** | Llama-family baseline at a similar size to Qwen3-8B |

## Metrics

### Automatic metrics

| Metric | What it measures |
| --- | --- |
| **ROUGE-1** | Unigram overlap with the reference summary |
| **ROUGE-2** | Bigram overlap with the reference summary |
| **ROUGE-L** | Longest-sequence overlap with the reference summary |
| **BERTScore** | Semantic similarity to the reference summary |

### LLM-judge rubric

Score each dimension independently from **1 (poor) to 5 (excellent)**.

| Dimension | Question |
| --- | --- |
| **Coherence** | Is the summary logically organized and easy to follow? |
| **Consistency** | Are the claims supported by the source paper? |
| **Fluency** | Is the writing grammatically correct and natural? |
| **Relevance** | Does it include the important information and avoid irrelevant details? |
| **Conciseness** | Is it brief and free of unnecessary repetition or elaboration? |

## Evaluation Protocol

1. Freeze a held-out test set before fine-tuning.
2. Run the **base model** and **fine-tuned model** on exactly the same papers.
3. Compute ROUGE-1/2/L and BERTScore against the same reference summaries.
4. Blind the model identity and use the same fixed LLM judge to score all five dimensions.
5. Report each metric separately and compare the change after fine-tuning.

## Results Table

| Model | R1 | R2 | RL | BERTScore | Coherence | Consistency | Fluency | Relevance | Conciseness |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base |  |  |  |  |  |  |  |  |  |
| Fine-tuned |  |  |  |  |  |  |  |  |  |
| Δ |  |  |  |  |  |  |  |  |  |

## Reference

Main experimental design reference:

- Wang, J., et al. (2025). **An Empirical Study of Many-to-Many Summarization with Large Language Models.** ACL 2025. https://aclanthology.org/2025.acl-long.555/

Wang et al. evaluate zero-shot and instruction-tuned models with **ROUGE-1, ROUGE-2, ROUGE-L, BERTScore**, and GPT-4o **1–5 ratings for conciseness, coherence, and relevance**. **Consistency** and **fluency** are included here as additional summary-quality dimensions commonly used in SummEval.

Additional rubric reference:

- Fabbri, A. R., et al. (2021). **SummEval: Re-evaluating Summarization Evaluation.** TACL 2021. https://aclanthology.org/2021.tacl-1.24/

Additional metric references:

- Lin, C.-Y. (2004). **ROUGE: A Package for Automatic Evaluation of Summaries.** *Text Summarization Branches Out (ACL Workshop).* https://aclanthology.org/W04-1013/
- Zhang, T., Kishore, V., Wu, F., Weinberger, K. Q., & Artzi, Y. (2020). **BERTScore: Evaluating Text Generation with BERT.** *International Conference on Learning Representations (ICLR 2020).* https://openreview.net/forum?id=SkeHuCVFDr
