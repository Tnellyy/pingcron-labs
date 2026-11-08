"""Run an isolated backup experiment; never uses production data or services."""
import argparse
import csv
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from common import utc, write_json
from fixture import build

HERE = Path(__file__).resolve().parent
CASES = ['control', 'wrong_source', 'masked_export_failure', 'stale_artifact',
         'corrupt_transfer', 'lost_object', 'not_started', 'checkin_unavailable']


def run_case(root, case, repetition):
    run_id = f'{case}-r{repetition}-{uuid.uuid4().hex[:8]}'
    root = root / run_id
    root.mkdir()
    build(root, 1041 + repetition)
    if case == 'not_started':
        result = {'run_id': run_id, 'case': case, 'repetition': repetition,
                  'exporter_exit': None, 'validator_exit': None, 'wrapper_exit': None,
                  'weak_wrapper_exit': None, 'upload_status': None,
                  'weak_checkin': {'status': 'not_attempted'},
                  'validated_checkin': {'status': 'not_attempted'},
                  'invocation': 'deliberately omitted by local harness; no cron simulation'}
        write_json(root / 'result.json', result)
        return result
    receiver_root = root / 'receiver'
    receiver_command = [sys.executable, str(HERE / 'receiver.py'), '--root', str(receiver_root), '--mode', case]
    with (root / 'receiver.stdout.txt').open('w', encoding='utf-8') as out, (root / 'receiver.stderr.txt').open('w', encoding='utf-8') as err:
        receiver = subprocess.Popen(receiver_command, stdout=out, stderr=err)
        try:
            deadline = time.monotonic() + 10
            while not (receiver_root / 'ready.json').exists():
                if receiver.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Receiver did not become ready')
                time.sleep(.02)
            base = json.loads((receiver_root / 'ready.json').read_text())['url']
            command = [sys.executable, str(HERE / 'workflow.py'), '--root', str(root), '--case', case,
                       '--run-id', run_id, '--receiver', base]
            start, clock = utc(), time.monotonic()
            workflow = subprocess.run(command, capture_output=True, text=True, timeout=60)
            (root / 'workflow.stdout.txt').write_text(workflow.stdout, encoding='utf-8')
            (root / 'workflow.stderr.txt').write_text(workflow.stderr, encoding='utf-8')
            write_json(root / 'workflow.process.json', {'command': command, 'started_at': start,
                       'ended_at': utc(), 'elapsed_seconds': time.monotonic() - clock, 'exit': workflow.returncode})
            result = json.loads((root / 'result.json').read_text(encoding='utf-8'))
            if result['wrapper_exit'] != workflow.returncode:
                raise AssertionError('Recorded wrapper exit differs from actual workflow process exit')
            result['repetition'] = repetition
            verification = root / 'verification.json'
            if verification.exists():
                result['verification'] = json.loads(verification.read_text(encoding='utf-8'))
            result['directory'] = str(root)
            write_json(root / 'result.json', result)
            return result
        finally:
            receiver.terminate()
            receiver.wait(timeout=10)
            write_json(root / 'receiver.process.json', {'command': receiver_command,
                       'exit': receiver.returncode, 'shutdown': 'terminated by harness after workflow; not a fault'})


def assert_expected(result):
    case = result['case']
    expected = {
        'control': (0, 0, 0, 'received', 'received'),
        'wrong_source': (0, 3, 1, 'received', 'not_attempted'),
        'masked_export_failure': (2, None, 1, 'received', 'not_attempted'),
        'stale_artifact': (0, 3, 1, 'received', 'not_attempted'),
        'corrupt_transfer': (0, 3, 1, 'received', 'not_attempted'),
        'lost_object': (0, 3, 1, 'received', 'not_attempted'),
        'not_started': (None, None, None, 'not_attempted', 'not_attempted'),
        'checkin_unavailable': (0, 0, 0, 'failed', 'failed'),
    }[case]
    observed = (result['exporter_exit'], result['validator_exit'], result['wrapper_exit'],
                result['weak_checkin']['status'], result['validated_checkin']['status'])
    assert observed == expected, (case, observed, expected)
    verification = result.get('verification', {})
    if case in ('control', 'wrong_source', 'stale_artifact', 'checkin_unavailable'):
        assert verification['integrity_rows'] == [['ok']]
        assert verification['foreign_key_rows'] == []
        assert verification['digest_matches'] is True
        assert set(verification['source_read_probes'].values()) == {'denied'}
    if case == 'wrong_source':
        assert verification['artifact_run_matches'] is True
        assert verification['semantic_match'] is False
        assert verification['actual']['expected_transaction_present'] is False
    if case == 'stale_artifact':
        assert verification['artifact_run_matches'] is False
        assert verification['semantic_match'] is False
    if case == 'corrupt_transfer':
        assert verification['digest_matches'] is False
    if case == 'lost_object':
        assert verification['download_status'] == 404


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case', choices=['all'] + CASES)
    p.add_argument('--output', required=True)
    p.add_argument('--repetitions', type=int, default=3)
    args = p.parse_args()
    if args.repetitions < 1:
        p.error('--repetitions must be positive')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = {str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(HERE.glob('*.py'))}
    write_json(output / 'environment.json', {'started_at': utc(), 'python': sys.version,
               'sqlite': sqlite3.sqlite_version, 'platform': platform.platform(), 'os_name': os.name,
               'executable': sys.executable, 'command': [sys.executable, *sys.argv],
               'source_sha256': sources, 'git_commit': None,
               'git_note': 'Standalone output artifact, not a Git working tree; exact source hashes recorded.'})
    results, failures = [], []
    for repetition in range(1, args.repetitions + 1):
        for case in CASES if args.case == 'all' else [args.case]:
            result = run_case(output, case, repetition)
            try:
                assert_expected(result)
                result['expectation_passed'] = True
            except AssertionError as exc:
                result['expectation_passed'] = False
                failures.append(str(exc))
            results.append(result)
            print(json.dumps({'case': case, 'repetition': repetition, 'exporter_exit': result['exporter_exit'],
                  'validator_exit': result['validator_exit'], 'wrapper_exit': result['wrapper_exit'],
                  'expectation_passed': result['expectation_passed']}), flush=True)
            write_json(output / 'RESULTS.json', results)
    fields = ['run_id', 'case', 'repetition', 'policy', 'exporter_exit', 'validator_exit', 'policy_exit',
              'upload_status', 'checkin_delivery_status', 'digest_matches', 'artifact_run_matches',
              'integrity_rows', 'foreign_key_rows', 'semantic_match', 'expectation_passed']
    with (output / 'RESULTS.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            for policy in ('weak', 'validated'):
                verifier = result.get('verification', {})
                writer.writerow({**{key: result.get(key) for key in ('run_id', 'case', 'repetition', 'exporter_exit', 'validator_exit', 'upload_status', 'expectation_passed')},
                    'policy': policy, 'policy_exit': result['weak_wrapper_exit' if policy == 'weak' else 'wrapper_exit'],
                    'checkin_delivery_status': result[policy + '_checkin']['status'],
                    **{key: json.dumps(verifier.get(key)) for key in ('digest_matches', 'artifact_run_matches', 'integrity_rows', 'foreign_key_rows', 'semantic_match')}})
    write_json(output / 'SUMMARY.json', {'completed_at': utc(), 'cases': len(results), 'policy_rows': len(results) * 2,
               'expectations_passed': len(results) - len(failures), 'failures': failures})
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
