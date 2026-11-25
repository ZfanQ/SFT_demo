"""Show read-only progress for the SciCommons delivery job over SSH."""

import argparse
from datetime import datetime
import json
import math
import re
import shlex
import subprocess
import sys
import time


REMOTE_SAMPLE = r"""
import json
from pathlib import Path
import re
import subprocess
import sys
import time

root = Path(sys.argv[1])
status = json.loads((root / 'run01/full_status.json').read_text())
protocol = json.loads((root / 'student_bundle/scoring_protocol.json').read_text())
checkpoints = root / 'run01' / ('full_' + status['selected_arm'])
batches = sum(
    re.fullmatch(r'\d{3}\.json', path.name) is not None
    for path in checkpoints.glob('*/*.json')
)
gpus = []
try:
    gpu = subprocess.run(
        ['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total',
         '--format=csv,noheader,nounits'],
        capture_output=True, text=True, timeout=5,
    )
    if gpu.returncode == 0:
        gpus = gpu.stdout.strip().splitlines()
except (OSError, subprocess.TimeoutExpired):
    pass
print(json.dumps({
    'job': (root / 'job_status.txt').read_text().strip(),
    'status': status,
    'group_size': protocol['group_size'],
    'batches': batches,
    'sampled_at': time.time(),
    'gpus': gpus,
}))
"""


def read_snapshot(host, run_dir):
    remote = shlex.join(['python3', '-', run_dir])
    result = subprocess.run(
        ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
         '-o', 'ConnectTimeout=8', host, remote],
        input=REMOTE_SAMPLE, capture_output=True, text=True, timeout=20,
    )
    if result.returncode:
        message = result.stderr.strip() or f'SSH exited with code {result.returncode}'
        raise RuntimeError(message.splitlines()[-1])
    return json.loads(result.stdout)


def bar(done, total):
    fraction = min(max(done / total, 0), 1)
    width = 24
    filled = round(width * fraction)
    return f"[{'#' * filled}{'-' * (width - filled)}] {100 * fraction:5.1f}%"


def duration(seconds):
    hours, minutes = divmod(max(0, round(seconds / 60)), 60)
    return f'{hours}h {minutes:02d}m'


def render(snapshot, papers, interests):
    status = snapshot['status']
    done = status['completed_papers']
    batches = snapshot['batches']
    total_batches = papers * math.ceil(interests / snapshot['group_size'])
    age = max(0, snapshot['sampled_at'] - status['started_unix'])
    sample_time = datetime.fromtimestamp(snapshot['sampled_at']).astimezone()
    lines = [
        f'SciCommons GPU24  |  {sample_time:%Y-%m-%d %H:%M:%S %Z}',
        f"State  {status['state']}  |  Prompt: {status['selected_arm']}  |  Elapsed: {duration(age)}",
        f'Papers     {bar(done, papers)}  {done:,} / {papers:,}',
        f'Batches    {bar(batches, total_batches)}  {batches:,} / {total_batches:,}',
        f"Verified scores from complete papers: {status['validated_scores']:,} / {papers * interests:,}",
    ]
    if status['state'] == 'running' and 0 < batches < total_batches:
        estimate = age * (total_batches - batches) / batches
        budget = status['deadline_unix'] - snapshot['sampled_at']
        lines.append(f'Estimated remaining: {duration(estimate)}  |  Time budget left: {duration(budget)}')
        if estimate > budget:
            lines.append('Current pace projects beyond the time budget.')
    for gpu in snapshot['gpus']:
        name, utilization, used, total = (item.strip() for item in gpu.rsplit(',', 3))
        usage = utilization if re.fullmatch(r'\d+', utilization) is None else f'{utilization}%'
        lines.append(f'GPU  {name}  |  VRAM {used} / {total} MiB  |  Utilization {usage}')
    return '\n'.join([*lines, f"Job status: {snapshot['job']}"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='gpu24')
    parser.add_argument('--run-dir', default='/data/SFT_demo/experiments/scicommons_delivery_20261125')
    parser.add_argument('--papers', type=int, default=200)
    parser.add_argument('--interests', type=int, default=2000)
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if min(args.interval, args.papers, args.interests) < 1:
        parser.error('interval, papers, and interests must be positive')

    last_view = ''
    while True:
        try:
            snapshot = read_snapshot(args.host, args.run_dir)
            last_view = render(snapshot, args.papers, args.interests)
            view = last_view
            finished = snapshot['status']['state'] != 'running' or 'exit=' in snapshot['job']
        except (RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
            view = f'{last_view}\n\nRead failed, last values may be stale: {error}'.lstrip()
            finished = False
            if args.once:
                print(view, file=sys.stderr)
                return 1
        if sys.stdout.isatty() and not args.once:
            print('\033[2J\033[H', end='')
        print(view, flush=True)
        if args.once or finished:
            return 0
        time.sleep(args.interval)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
