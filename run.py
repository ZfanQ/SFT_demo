#!/usr/bin/env python3
"""Run the frozen relevance tools with current repository paths."""
import argparse
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('task', choices=['audit-relevance', 'resume-relevance'])
a = p.parse_args()
script = 'compare_relevance_population.py' if a.task == 'audit-relevance' else 'review_relevance_population.py'
cmd = [sys.executable, '-B', str(ROOT/'src'/script), '--root', str(ROOT/'experiments/relevance/relevance_review_full_20261106'), '--source', str(ROOT/'experiments/performance/feed_matrix_20261031')]
if a.task == 'resume-relevance':
    cmd += ['--pilot', str(ROOT/'experiments/relevance/relevance_review_20261105')]
raise SystemExit(subprocess.call(cmd, cwd=ROOT))
