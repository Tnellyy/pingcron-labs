"""Deliberate bug comparator: run a command, retain its failure, then exit 0."""
import argparse
import subprocess
import sys
import time
from pathlib import Path
from common import utc, write_json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    root = Path(args.root)
    start, clock = utc(), time.monotonic()
    child = subprocess.run(command, capture_output=True, text=True, timeout=30)
    (root / 'exporter.stdout.txt').write_text(child.stdout, encoding='utf-8')
    (root / 'exporter.stderr.txt').write_text(child.stderr, encoding='utf-8')
    write_json(root / 'exporter.process.json', {'command': command, 'started_at': start,
        'ended_at': utc(), 'elapsed_seconds': time.monotonic() - clock, 'exit': child.returncode})
    print('Ignoring exporter failure: deliberate weak comparator; child exit=' + str(child.returncode))
    sys.exit(0)
