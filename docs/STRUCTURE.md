# Repository Layout

Reports and raw evidence live together under `experiments/relevance/`, `experiments/performance/` and `experiments/summaries/`. Each dated run is a frozen research record. Source code lives in `src/`; original five-paper examples are in `examples/five_paper_baseline/`.

## Current commands

Run from the repository root:

```sh
python3 run.py audit-relevance
python3 run.py resume-relevance
python3 -B -m unittest discover -s tests
```

The launcher supplies the reorganized input paths. Accepted judgments are reused. Frozen driver defaults and historical execution notes retain the paths used for their original runs; use the launcher for the current full relevance review. For other scripts, supply current input/output locations explicitly through their CLI arguments.

## Historical paths

`layout_migration.json` records each move and the pre-move SHA-256 of preserved files. Experiment records, raw requests, source snapshots and judge drivers retain their original content. Relative links inside frozen reports describe their historical layout; the current report directory and experiment indexes supply navigation across runs.

The GPU24 shared-results layout is unchanged by this repository reorganization.
