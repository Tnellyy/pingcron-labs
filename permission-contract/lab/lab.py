"""Run predetermined calls; independently compare durable state to literal expectations."""
import argparse
import csv
import hashlib
import http.client
import json
import os
import platform
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRITE = {'action': 'write', 'resource': 'resource-A', 'value': 'changed-by-fixture'}
INTENT_WRITE = {**WRITE, 'client_metadata': {'prompt_intent': 'read_only'}}
CASES = {
    'read_control': ('synthetic-reader-A', {'action': 'read', 'resource': 'resource-A'}, 200, False, 'allowed'),
    'broad_prompt_write': ('synthetic-broad-A', INTENT_WRITE, 200, True, 'allowed'),
    'scoped_write_denied': ('synthetic-reader-A', INTENT_WRITE, 403, False, 'scope_denied'),
    'tenant_read_denied': ('synthetic-reader-A', {'action': 'read', 'resource': 'resource-B'}, 403, False, 'resource_denied'),
    'claimed_scope_denied': ('synthetic-reader-A', {**WRITE, 'client_metadata': {'claimed_scope': ['read', 'write']}}, 403, False, 'scope_denied'),
    'hint_does_not_restrict': ('synthetic-broad-A', {**WRITE, 'client_metadata': {'readOnlyHint': True}}, 200, True, 'allowed'),
    'hint_cannot_elevate': ('synthetic-reader-A', {**WRITE, 'client_metadata': {'readOnlyHint': False}}, 403, False, 'scope_denied'),
    'unknown_credential': ('synthetic-unknown', {'action': 'read', 'resource': 'resource-A'}, 401, False, 'unknown_credential'),
}
INITIAL_ROWS = [
    {'id': 'resource-A', 'tenant': 'tenant-A', 'value': 'A-private-fixture', 'version': 0},
    {'id': 'resource-B', 'tenant': 'tenant-B', 'value': 'B-private-fixture', 'version': 0},
]


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def snapshot(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        return {name: [dict(r) for r in db.execute('SELECT * FROM ' + name + ' ORDER BY ' + ('credential' if name == 'credentials' else 'id'))]
                for name in ('resources', 'mutations', 'audit', 'credentials')}
    finally:
        db.close()


def run_case(root, name, repetition):
    credential, request, expected_status, changes, decision = CASES[name]
    run_id = '{}-r{}-{}'.format(name, repetition, uuid.uuid4().hex[:8])
    directory = root / run_id
    directory.mkdir()
    db = directory / 'state.sqlite'
    ready = directory / 'ready.json'
    expected_rows = [dict(row) for row in INITIAL_ROWS]
    if changes:
        expected_rows[0].update(value='changed-by-fixture', version=1)
    expected_body = ({'error': 'unauthorized' if expected_status == 401 else 'forbidden'} if expected_status != 200 else
                     {'resource': 'resource-A', 'value': 'changed-by-fixture' if changes else 'A-private-fixture', 'version': int(changes)})
    expected_mutations = ([{'id': 1, 'resource': 'resource-A', 'old_value': 'A-private-fixture', 'new_value': 'changed-by-fixture'}] if changes else [])
    plan = {'case': name, 'run_id': run_id, 'synthetic_credential': credential, 'request': request,
            'expected_status': expected_status, 'expected_body': expected_body, 'expected_resources': expected_rows,
            'expected_mutations': expected_mutations, 'expected_decision': decision}
    save(directory / 'plan.json', plan)
    command = [sys.executable, '-u', str(HERE / 'receiver.py'), '--db', str(db), '--ready', str(ready)]
    result = {'case': name, 'run_id': run_id, 'repetition': repetition, 'plan': plan, 'command': command}
    with open(directory / 'receiver-stdout.jsonl', 'w', encoding='utf-8') as stdout, open(directory / 'receiver-stderr.txt', 'w', encoding='utf-8') as stderr:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, text=True, encoding='utf-8')
        try:
            deadline = time.monotonic() + 10
            while True:
                if process.poll() is not None:
                    raise RuntimeError('receiver exited before readiness')
                try:
                    server = json.loads(ready.read_text(encoding='utf-8'))
                    break
                except (FileNotFoundError, json.JSONDecodeError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError('receiver readiness')
                    threading.Event().wait(0.01)
            result['before'] = snapshot(db)
            connection = http.client.HTTPConnection('127.0.0.1', server['port'], timeout=10)
            try:
                headers = {'Authorization': 'Bearer ' + credential, 'Content-Type': 'application/json'}
                body = json.dumps(request)
                save(directory / 'request.json', {'method': 'POST', 'url': 'http://127.0.0.1:{}/call'.format(server['port']),
                                                  'headers': headers, 'body': body})
                connection.request('POST', '/call', body, headers)
                response = connection.getresponse()
                raw = response.read().decode('utf-8')
                result['http'] = {'status': response.status, 'headers': dict(response.getheaders()), 'body_raw': raw, 'body': json.loads(raw)}
                save(directory / 'response.json', result['http'])
            finally:
                connection.close()
        except Exception as error:
            result['error'] = {'type': type(error).__name__, 'message': str(error)}
        finally:
            if process.poll() is None:
                process.stdin.write('stop\n')
                process.stdin.flush()
            result['receiver_exit'] = process.wait(timeout=10)
            result['receiver_pid'] = process.pid
            process.stdin.close()
    result['after'] = snapshot(db)
    observed_http = result.get('http', {})
    before = result.get('before', {})
    after = result['after']
    checks = {
        'receiver_exit_zero': result['receiver_exit'] == 0,
        'initial_fixture_matches_independent_plan': before.get('resources') == INITIAL_ROWS and before.get('mutations') == [],
        'status_matches_plan': observed_http.get('status') == expected_status,
        'body_matches_plan': observed_http.get('body') == expected_body,
        'durable_resources_match_plan': after['resources'] == expected_rows,
        'durable_mutations_match_plan': after['mutations'] == expected_mutations,
        'audit_matches_plan': after['audit'] == [{'id': 1, 'action': request['action'], 'resource': request['resource'], 'decision': decision}],
        'server_credential_policy_unchanged': before.get('credentials') == after['credentials'],
        'denials_have_no_resource_payload': expected_status == 200 or (set(observed_http.get('body', {})) == {'error'}
                                and 'private-fixture' not in observed_http.get('body_raw', '')),
    }
    result['checks'] = checks
    result['passed'] = 'error' not in result and all(checks.values())
    save(directory / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--case', choices=list(CASES))
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats must be positive')
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))}
    save(root / 'environment.json', {'utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
          'sqlite': sqlite3.sqlite_version, 'platform': platform.platform(), 'executable': sys.executable,
          'cwd': os.getcwd(), 'argv': sys.argv, 'source_sha256': hashes,
          'scope': 'Synthetic local HTTP policy contract; no model, MCP, OAuth, production credentials or customer data'})
    results = []
    for name in ([args.case] if args.case else CASES):
        for repetition in range(1, args.repeats + 1):
            result = run_case(root, name, repetition)
            results.append(result)
            save(root / 'RESULTS.json', results)
            print(json.dumps({'run_id': result['run_id'], 'passed': result['passed'], 'error': result.get('error')}), flush=True)
    with open(root / 'RESULTS.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['case', 'run_id', 'passed', 'status', 'mutations', 'value_A', 'value_B'])
        writer.writeheader()
        for result in results:
            writer.writerow({'case': result['case'], 'run_id': result['run_id'], 'passed': result['passed'],
                             'status': result.get('http', {}).get('status'), 'mutations': len(result['after']['mutations']),
                             'value_A': result['after']['resources'][0]['value'], 'value_B': result['after']['resources'][1]['value']})
    summary = {'total': len(results), 'passed': sum(r['passed'] for r in results), 'failed': sum(not r['passed'] for r in results),
               'source_sha256': hashes, 'meaning': 'Predetermined requests matched this deliberately implemented toy policy contract.'}
    save(root / 'SUMMARY.json', summary)
    print(json.dumps(summary), flush=True)
    return int(summary['failed'] != 0)


if __name__ == '__main__':
    sys.exit(main())
