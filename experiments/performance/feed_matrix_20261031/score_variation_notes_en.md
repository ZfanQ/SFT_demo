# Qualitative Checks of Threshold-Flip Cases

Date: October 31, 2026. These are qualitative examples from the frozen inputs, not gold relevance annotations.

## Qwen3-8B: neuroscience scope boundary

The independent audit finds one unique paper/profile combination crossing the selected relevance threshold (score >=2): `paper012` under the neuroscience profile. The 2-request run assigns 1; both the 4- and 8-request runs assign 2. This is one affected input pair, appearing in two configuration comparisons, not two different papers.

The frozen author abstract describes a glioblastoma study of an engineered oncolytic virus, cell and murine experiments, immune mechanisms and combination with CAR-T cells. The supplied neuroscience interest profile covers brain/neural mechanisms, neurodegeneration, cognition, stroke, neural injury and treatments or biomarkers for neurological disorders, but does not explicitly define inclusion or exclusion of neuro-oncology.

This provides a plausible scope-boundary interpretation of the 1-versus-2 difference. It does not establish which score is correct or demonstrate that batching caused worse relevance judgments. This check is an assistant's qualitative reading of the frozen abstract/profile, not an independent human gold annotation or clinical assessment.

The current profile and prompts remain unchanged, preserving the controlled comparison. A later relevance-quality study should predefine whether overlapping domains such as neuro-oncology count as peripheral or relevant, use independent annotations, and then evaluate all candidate configurations against the same labels. It should not edit the profile halfway through the current benchmark or treat the two-request scores as ground truth.

## Qwen3.5-9B: peripheral pathway reference

In the completed oncology block of the separate llama.cpp run, `paper102` scores 2 with two requests and 1 with four/eight requests. The supplied abstract studies vaccine-associated autoantibody profiles in healthy adults, including antigens linked to autoimmune and cancer-related pathways. It is not a cancer-treatment cohort in the supplied abstract. A peripheral relevance score is therefore a plausible interpretation of the stated oncology profile, despite the cancer-related pathway references. This does not establish a gold score, but illustrates why a changed high-concurrency score cannot automatically be counted as a new error.
