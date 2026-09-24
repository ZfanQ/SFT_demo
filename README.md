# SciCommons Small-Model Scientific Summarization

## Project Overview

This project investigates whether a locally deployable small language model can generate useful and factually grounded summaries for papers displayed in the [SciCommons feed](https://feed.scicommons.org/scicommons/default).

The central idea is to use a stronger large language model as a teacher, generate quality-controlled summaries for scientific papers, and then fine-tune smaller open-weight models on the resulting data. The project will study not only whether distillation improves summary quality, but also **which models work best, which evaluation rubrics are reliable, which paper types remain difficult, and whether targeted tuning can correct those weaknesses**.

The proposed research sequence is:

> **Models -> Rubrics -> Paper Types -> Targeted Tuning -> Evaluation -> Deployment**

Rather than treating every teacher-generated summary as a gold label, the project will explicitly validate, filter, and audit the synthetic training data.

The work is divided into two major phases:

- **Stage 1 - Baseline and benchmark:** no model training; establish a fixed benchmark, strong prompting baselines, and a validated evaluation framework.
- **Stage 2 - Distillation and targeted tuning:** generate quality-controlled teacher data, fine-tune student models, diagnose errors by paper type, and target the next training round at observed weaknesses.

This separation is important: fine-tuning should be judged against the strongest reproducible prompted baseline, not against an intentionally weak zero-shot system.

## Motivation

Scientific abstracts are written primarily for publication and are not always optimized for rapid paper discovery. A SciCommons feed summary should help a reader answer:

1. What problem does this paper study?
2. What method or data does it use?
3. What are the main findings?
4. What limitations or qualifications should the reader know?
5. Is the paper relevant enough to open and read?

Semantic Scholar's [TLDR feature](https://www.semanticscholar.org/product/tldr) demonstrates the value of showing a one-sentence machine-generated summary beside a paper. This project extends that idea by examining structured summaries, factual grounding, model efficiency, and domain-specific adaptation for SciCommons.

## Research Questions

### RQ1: Model capability

How well do small open-weight models of different sizes summarize scientific papers before and after supervised fine-tuning?

### RQ2: Evaluation reliability

Which combination of automatic metrics, LLM-based rubrics, and human review best captures factuality, relevance, readability, and usefulness?

### RQ3: Paper-type variation

Do summary quality and error patterns differ across disciplines and paper types, such as empirical studies, reviews, methodological papers, and theoretical papers?

### RQ4: Targeted tuning

Can a second training stage focused on the student model's observed weaknesses improve performance more efficiently than adding randomly selected synthetic examples?

### RQ5: Quality-efficiency trade-off

How closely can a local small model approach teacher-model quality while reducing inference latency, memory requirements, and marginal cost?

## Proposed Summary Task

The first version will use the paper title and abstract as input. Full-text summarization can be studied later after the abstract-level pipeline is stable.

The target output will contain two levels:

- **Feed TLDR:** a concise 40-70 word summary for paper discovery.
- **Expanded summary:** a structured 150-250 word summary covering the problem, method, findings, and stated limitations.

Example output schema:

```json
{
  "tldr": "A concise statement of the research question, approach, and central finding.",
  "research_question": "The question, hypothesis, or gap addressed by the paper.",
  "methods": "The main data, experiment, participants, or analytical approach.",
  "main_findings": [
    "Main finding 1",
    "Main finding 2"
  ],
  "limitations": ["A limitation explicitly stated or directly supported by the source."],
  "significance": "Why the reported contribution matters, without adding unsupported implications.",
  "keywords": ["keyword 1", "keyword 2"]
}
```

During dataset construction, the teacher will also return supporting evidence spans. These spans may not be displayed in the final feed, but they can be used to filter unsupported claims and audit factual consistency.

## Study Design

### Step 1: Models and prompting baselines

Stage 1 will not involve fine-tuning. We will first establish model and prompting baselines before generating a large synthetic dataset.

Candidate student models may include:

| Role | Approximate size | Purpose |
| --- | ---: | --- |
| Small baseline | 1.5B-4B | Estimate the lowest viable deployment cost |
| Primary student | 8B | Main fine-tuning baseline supported comfortably by the H100 |
| Capacity baseline | 12B-14B | Test whether model selection or scale closes the gap without tuning |
| Teacher | Strong API model or large open model | Generate, critique, and revise training summaries |

Initial candidates include Qwen3-4B, Qwen3-8B, Qwen3-14B, and Gemma 3 12B. Qwen3-8B is the provisional primary student because it is large enough for a meaningful scientific-summarization study while remaining practical for LoRA/QLoRA training and quantized deployment. The final choice will be made after zero-shot and few-shot pilot evaluation.

Initial baselines:

- Untuned student with a zero-shot prompt
- Untuned student with a few-shot prompt
- Teacher model with the same task specification
- Public scientific summarization baseline using SciTLDR

Two prompt conditions will be fixed before fine-tuning:

1. **Simple prompt:** requests the required summary fields and source grounding with minimal instruction.
2. **Structured prompt:** defines information priorities, unsupported-content rules, handling of unstated limitations, length limits, and exact output schema.

The key Stage 2 comparison will therefore be:

```text
Qwen3-8B + simple prompt
        vs.
Qwen3-8B + structured prompt
        vs.
Qwen3-8B + QLoRA fine-tuning
```

### Fixed Stage 1 benchmark

Before prompt optimization or training, a fixed held-out benchmark of approximately **50-100 papers** will be created. It must remain excluded from teacher-data generation and fine-tuning.

The benchmark will include short, medium, long, highly technical, result-heavy, and method-heavy papers. If the project initially focuses on one scientific domain, it will still vary publication source, study design, methodology, input length, and result complexity.

Every evaluated model must receive the same cleaned representation. The primary benchmark will use `title + abstract`. If reliable XML or section extraction is available, an additional full-text subset may use:

```json
{
  "paper_id": "paper_001",
  "title": "...",
  "abstract": "...",
  "introduction": "...",
  "methods": "...",
  "results": "...",
  "discussion": "...",
  "metadata": {
    "source": "PMC",
    "domain": "neuroscience",
    "paper_type": "empirical"
  }
}
```

### Step 2: Rubrics

Before large-scale data generation, a common evaluation rubric will be defined and tested on a manually reviewed pilot set.

| Dimension | Question | Example measurement |
| --- | --- | --- |
| Factual consistency | Is every generated claim supported by the source? | Claim-evidence verification, AlignScore, human review |
| Relevance | Does the summary cover the most important contribution? | Key-point coverage, rubric score |
| Completeness | Are the research question, method, and main result represented? | Required-field coverage |
| Readability | Can a researcher outside the narrow specialty understand it? | Human/LLM rubric, readability statistics |
| Conciseness | Does the summary avoid repetition and unnecessary detail? | Length compliance, rubric score |
| Calibration | Does it avoid overstating causality, certainty, or generalizability? | Error labels and human review |
| Format reliability | Can the output be used directly by the application? | Valid JSON and schema compliance rate |
| Efficiency | Is the model economical enough for feed-scale inference? | Latency, throughput, GPU memory, model size, and cost |

ROUGE and BERTScore will be reported where references are available, but they will not be treated as sufficient measures of factual correctness. A subset of outputs will be evaluated blindly by humans to check whether automatic and LLM-based scores agree with researcher preferences.

For Stage 1, the main rubric will use an interpretable 100-point scale:

| Dimension | Weight | Operational interpretation |
| --- | ---: | --- |
| Factuality | 40 | Important claims are supported; numbers, comparisons, and causal language are correct |
| Coverage | 25 | Research question, methods, main findings, limitations, and significance are represented |
| Importance/relevance | 15 | Central contributions are prioritized over secondary details |
| Readability/conciseness | 10 | The output is clear, non-repetitive, and appropriately compressed |
| Format/instruction following | 10 | The JSON is valid, fields and types are correct, and length constraints are followed |

Individual dimensions will always be reported alongside the total. A fluent but factually unreliable model should not be obscured by a similar overall score.

#### Claim-level factuality

Each generated summary will also be decomposed into atomic claims. Every claim will be assigned one of:

- `SUPPORTED`
- `PARTIALLY_SUPPORTED`
- `UNSUPPORTED`

Example record:

```json
{
  "claim": "The intervention reduced mortality by 28%.",
  "status": "SUPPORTED",
  "evidence": "...",
  "section": "Results"
}
```

This produces interpretable error counts and training examples, rather than only a document-level factuality score.

#### Absolute and pairwise evaluation

The evaluator will perform both:

- **Absolute scoring:** apply the fixed rubric independently to each summary.
- **Blind pairwise comparison:** compare Summary A and Summary B with model identities hidden and return `A`, `B`, or `Tie` with evidence-based justification.

Pairwise win rates will make the final comparison between the prompted and fine-tuned Qwen3-8B easier to interpret. The teacher remains a reference system, not ground truth.

### Step 3: Different paper types

The evaluation set will be stratified so that average performance does not hide systematic weaknesses.

Possible dimensions include:

- Discipline: biomedical science, computer science, social science, and other SciCommons categories
- Research type: empirical, review, methodological, theoretical, and dataset/resource paper
- Input length: short, medium, and long abstracts
- Result style: quantitative, qualitative, mixed-method, or no direct empirical result
- Evidence density: many numerical findings versus primarily conceptual contributions
- Accessibility: specialist terminology versus broadly readable language

Error analysis will use a controlled taxonomy:

- Unsupported or hallucinated claim
- Incorrect number, population, or comparison
- Causal overstatement
- Omitted central finding
- Method-result confusion
- Missing qualification or limitation
- Excessive jargon
- Vague or generic summary
- Invalid structure or excessive length

This stage will identify whether one general summarizer is sufficient or whether certain paper groups require targeted examples, routing, or domain adapters.

### Step 4: Targeted tuning

The first fine-tuning stage will use quality-controlled teacher responses as standard supervised fine-tuning data. This is best described as **black-box response distillation** or **synthetic-data distillation**, because the student observes teacher-generated text rather than the teacher's internal logits.

After the initial student is evaluated, a second targeted dataset will be constructed:

1. The student generates summaries for unseen papers.
2. The teacher identifies unsupported claims, omissions, and style problems.
3. The teacher revises the student's summary using only the source paper.
4. High-quality correction examples are verified and added to the training set.
5. The student is fine-tuned again and compared with a random-data expansion baseline.

This creates a student-error-conditioned training loop inspired by on-policy distillation, while remaining feasible when the teacher is a black-box API.

Potential tuning variants:

- Unfiltered teacher-generated SFT data
- Quality-filtered teacher-generated SFT data
- Balanced data across paper categories
- Student-error-conditioned correction data
- Domain-specific LoRA adapters, if clear discipline-level differences emerge
- Preference or contrastive training using accepted and rejected summaries, if reliable pairs can be constructed

## Synthetic Data Pipeline

### Source collection

The initial dataset will use SciCommons paper metadata and abstracts. Public datasets will be used for external validation rather than mixed indiscriminately into the final test set.

### Teacher generation

The teacher prompt will require the model to:

- Use only information in the supplied title and abstract
- Preserve important numbers and comparison directions
- Avoid converting association into causation
- Mark absent information as `Not stated`
- Return a valid structured output
- Associate each important claim with a supporting source span

### Quality filtering

Generated samples will pass through:

1. JSON/schema validation
2. Length and required-field checks
3. Numerical and entity consistency checks
4. Claim-evidence semantic alignment checks
5. Duplicate and near-duplicate detection
6. LLM-based rubric scoring
7. Human audit on a stratified sample

The project will compare a larger unfiltered synthetic dataset with a smaller quality-controlled dataset to test whether curation is more valuable than raw scale.

## Experimental Matrix

| ID | Model | Training data | Purpose |
| --- | --- | --- | --- |
| B0 | Base student | None; zero-shot | Minimum baseline |
| B1 | Base student | None; few-shot | Prompting baseline |
| T | Teacher | None | Quality and cost reference |
| M1 | Student SFT | Raw synthetic summaries | Test basic response distillation |
| M2 | Student SFT | Filtered synthetic summaries | Test the value of data curation |
| M3 | Student SFT | Filtered + targeted correction data | Test student-error-conditioned tuning |
| M4 | Larger student | Best-performing dataset | Test capacity versus deployment cost |

Important ablations:

- Raw versus filtered teacher data
- Random additional data versus targeted correction data
- 1.5B-1.7B versus 4B versus 7B-8B student
- TLDR-only versus structured multi-field output
- General training mixture versus paper-type-balanced mixture

## Data Splitting and Leakage Control

Train, validation, and test sets will be separated by paper identity before teacher generation. Where metadata permits, the project will also consider author, venue, topic, and publication-time overlap.

The preferred final evaluation is a later-period or otherwise untouched SciCommons sample. Public benchmark test sets will never be used to generate training targets or tune prompts.

## Training and Infrastructure

Training will run remotely on the provided Linux H100 system. Development can be performed from a local computer using SSH and VS Code Remote SSH.

Proposed stack:

- PyTorch and Hugging Face Transformers
- TRL `SFTTrainer`
- PEFT with LoRA or QLoRA
- FlashAttention where supported
- MLflow or Weights & Biases for experiment tracking
- `tmux` or the server's job scheduler for persistent runs
- vLLM for server-side batch inference
- llama.cpp or MLX for local quantized deployment tests

The first implementation will use LoRA/QLoRA rather than full-parameter fine-tuning. H100 capacity will be used for controlled model-size comparisons, longer-context experiments, and faster batch evaluation rather than unnecessary model scaling.

## Evaluation Protocol

### Automatic evaluation

- ROUGE-1, ROUGE-2, and ROUGE-L
- BERTScore
- Factual alignment or entailment score
- Key information and required-field coverage
- Numerical consistency
- Output-schema success rate
- Summary length and compression ratio

### LLM-based evaluation

An evaluator model will score each output independently on factuality, relevance, completeness, readability, conciseness, and calibration. The evaluation prompt and rubric will be fixed before final testing.

To reduce self-preference effects, the evaluator should differ from the summary generator where feasible, and candidate identities should be hidden.

### Human evaluation

A stratified subset of approximately **20-30 benchmark papers** will receive detailed manual inspection during Stage 1. The sample can be expanded in the final stage if reviewer capacity permits. Evaluators will compare the teacher, base student, and fine-tuned student without seeing model names.

Human evaluation will also test whether the summary is useful for the actual product decision: **Would this summary help a researcher decide whether to open the paper?**

Agreement between human and LLM-judge scores will be reported. If they disagree substantially, LLM-based scores will not be treated as a reliable primary outcome.

### Efficiency evaluation

- Peak GPU/CPU memory
- Model and adapter size
- Tokens per second
- Mean and percentile latency per paper
- Batch throughput
- Teacher data-generation cost
- Estimated marginal cost per 1,000 SciCommons papers

## Deployment Concept

The selected student model will be merged or loaded with its adapter and exposed through a simple inference service. The service will accept paper metadata and return schema-valid summaries for the SciCommons frontend.

Possible deployment flow:

```text
SciCommons paper ingestion
        -> summarization queue
        -> local student-model API
        -> schema and safety validation
        -> stored summary
        -> feed TLDR / expanded summary
```

Summaries should be generated asynchronously and cached rather than recomputed whenever a user opens the feed.

## Reproducible Record Formats

Every model output should retain enough provenance to reproduce it:

```json
{
  "paper_id": "paper_001",
  "model": "qwen3_8b",
  "model_revision": "...",
  "prompt_version": "structured_v1",
  "decoding": {
    "temperature": 0.0,
    "max_new_tokens": 512
  },
  "summary": {
    "research_question": "...",
    "methods": "...",
    "main_findings": ["..."],
    "limitations": ["..."],
    "significance": "...",
    "tldr": "..."
  }
}
```

Evaluation records should retain both aggregate scores and identified errors:

```json
{
  "paper_id": "paper_001",
  "model": "qwen3_8b",
  "rubric_version": "v1",
  "scores": {
    "factuality": 33,
    "coverage": 20,
    "importance": 12,
    "readability": 9,
    "format": 10
  },
  "overall": 84,
  "unsupported_claims": ["..."]
}
```

## Suggested Repository Structure

```text
scicommons-summarization/
├── README.md
├── configs/
│   ├── models/
│   └── training/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── benchmark/
│   └── synthetic/
├── prompts/
│   ├── simple_prompt.txt
│   ├── structured_prompt.txt
│   ├── teacher_prompt.txt
│   └── evaluator_prompt.txt
├── scripts/
│   ├── prepare_papers.py
│   ├── generate_teacher_data.py
│   ├── run_baselines.py
│   └── train_sft.py
├── evaluation/
│   ├── evaluate_format.py
│   ├── evaluate_claims.py
│   ├── evaluate_llm.py
│   └── evaluate_pairwise.py
├── outputs/
│   └── <model>/<prompt_version>/
├── results/
│   ├── scores.jsonl
│   ├── pairwise_results.json
│   └── summary.csv
└── deployment/
    └── inference_api/
```

Large paper files, generated datasets, model weights, and credentials should not be committed directly to Git. The repository should track manifests, preprocessing scripts, configuration files, checksums, and small examples needed for reproducibility.

## Suggested Milestones

### Milestone 1: Task and rubric definition

- Inspect SciCommons paper data and frontend requirements
- Finalize the TLDR and expanded-summary schemas
- Build and manually review a small pilot set
- Freeze the initial rubric

Stage 1 is complete when:

- The held-out benchmark is fixed and versioned
- Every baseline model has been evaluated on identical inputs
- Simple and structured prompts have been compared
- Factuality, coverage, importance, readability, and format scores are available separately
- Claim-level and pairwise evaluation are reproducible
- At least 20-30 benchmark papers have received human review
- Model revisions, prompts, decoding settings, and evaluation records are retained
- The strongest Stage 1 baseline is identified before fine-tuning begins

### Milestone 2: Public benchmark reproduction

- Reproduce a small-model baseline on SciTLDR
- Validate training, inference, and evaluation scripts on the H100
- Establish zero-shot and few-shot baselines

### Milestone 3: SciCommons synthetic dataset

- Generate the first teacher-labeled dataset
- Implement schema, numerical, and evidence filters
- Audit a stratified sample and refine the teacher prompt

### Milestone 4: Initial distillation experiments

- Fine-tune the primary student model
- Compare raw and filtered synthetic data
- Analyze performance by paper type and error category

### Milestone 5: Targeted tuning

- Generate student summaries on a new sample
- Create teacher critiques and corrected targets
- Compare targeted correction with random data expansion

### Milestone 6: Final evaluation and prototype

- Complete blinded human evaluation
- Measure quality-efficiency trade-offs
- Quantize and deploy the selected student
- Integrate a prototype endpoint with SciCommons

## Expected Contributions

The project aims to contribute:

1. A clearly defined summarization task for the SciCommons paper feed
2. A quality-controlled synthetic scientific-summary dataset
3. A reproducible H100-based training and evaluation pipeline
4. Evidence on the effect of model size and synthetic-data filtering
5. A paper-type and error-specific evaluation of small summarizers
6. A targeted correction strategy based on observed student weaknesses
7. A locally deployable summarization model and integration prototype

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Teacher hallucinations become training labels | Require evidence spans, automatic checks, and human audits |
| ROUGE rewards copying rather than usefulness | Combine semantic, factual, rubric, and human evaluation |
| LLM judge favors its own writing style | Use a different evaluator where possible and validate against humans |
| Paper types are unevenly represented | Stratified sampling and paper-type reporting |
| Full papers exceed practical context limits | Begin with abstracts; add section-based full-text processing later |
| Student memorizes repeated papers or authors | Paper-level splitting plus metadata-based leakage checks |
| Small model produces invalid structured outputs | Constrained schema, validation, retry policy, and format-focused examples |
| Training improves quality but not deployment value | Report latency, throughput, memory, and cost alongside text metrics |

## Key References and Resources

### Scientific summarization

- Cachola et al. (2020), [TLDR: Extreme Summarization of Scientific Documents](https://aclanthology.org/2020.findings-emnlp.428/)
- AllenAI, [SciTLDR Dataset and Code](https://github.com/allenai/scitldr)
- BioLaySumm, [Biomedical Lay Summarization](https://biolaysumm.org/)
- LongSumm, [Scientific Document Summarization Shared Task](https://github.com/guyfe/LongSumm)

### Distillation and synthetic supervision

- Liu et al. (2023), [On Learning to Summarize with Large Language Models as References](https://arxiv.org/abs/2305.14239)
- Sclar et al. (2022), [Referee: Reference-Free Sentence Summarization with Symbolic Knowledge Distillation](https://arxiv.org/abs/2210.13800)
- Agarwal et al., [On-Policy Distillation of Language Models](https://openreview.net/pdf?id=XE54YS688c)
- Zhu et al., [Factual Dialogue Summarization via Learning from Large Language Models](https://arxiv.org/abs/2406.14709)
- [LLM Distillation Playbook](https://github.com/predibase/llm_distillation_playbook)

### Evaluation and implementation

- Zhang et al., [BERTScore](https://arxiv.org/abs/1904.09675)
- Zha et al. (2023), [AlignScore](https://aclanthology.org/2023.acl-long.634/)
- Hugging Face, [TRL SFTTrainer](https://huggingface.co/docs/trl/sft_trainer)
- Hugging Face, [Generalized Knowledge Distillation Trainer](https://huggingface.co/docs/trl/gkd_trainer)
- [Qwen3 Scientific Summarization Example](https://github.com/AndreyGermanov/qwen3_scientific_summarization)

## Open Decisions for Discussion

The following decisions should be confirmed before large-scale generation or training:

1. Is the primary audience a specialist researcher, a cross-disciplinary researcher, or the general public?
2. Should the initial task summarize only abstracts or include available full text?
3. Is the desired product mainly a one-sentence TLDR, a structured expanded summary, or both?
4. Which disciplines and paper types should be prioritized in the first release?
5. Which teacher model or models are available, and what generation budget is acceptable?
6. What level of human review can domain experts provide?
7. Is the final deployment target the H100 server, a lower-cost GPU, CPU, or researchers' local devices?
8. Should the project prioritize the strongest final model or a controlled research comparison across model sizes and training strategies?

## Current Status

This document is a proposed research and implementation plan. Model selection, dataset size, teacher model, output schema, and evaluation thresholds remain subject to pilot testing and supervisor feedback.
