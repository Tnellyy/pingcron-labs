import argparse
import concurrent.futures
import hashlib
import json
import platform
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from common import utc, write_json
from ledger import snapshot

HERE = Path(__file__).resolve().parent
CASES = ['control', 'after_commit_no_key', 'after_commit_per_attempt_key',
         'after_commit_stable_key', 'before_commit_timeout', 'payload_mismatch',
         'distinct_intents_distinct_keys', 'distinct_intents_reused_key',
         'concurrent_stable_key', 'crash_before_commit', 'crash_after_commit', 'dedup_record_removed']


def command_run(command, root, label):
    start = utc()
    child = subprocess.run(command, capture_output=True, text=True, timeout=30)
    (root / (label + '.stdout.txt')).write_text(child.stdout, encoding='utf-8')
    (root / (label + '.stderr.txt')).write_text(child.stderr, encoding='utf-8')
    write_json(root / (label + '.process.json'), {'command': command, 'started_at': start,
               'ended_at': utc(), 'exit': child.returncode})
    return child


def control(url, action, data):
    request = urllib.request.Request(url + '/control/' + action, data=json.dumps(data).encode(),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


class Receiver:
    def __init__(self, root, instance):
        self.root, self.instance = root, instance
        self.out = (root / (instance + '.stdout.txt')).open('w', encoding='utf-8')
        self.err = (root / (instance + '.stderr.txt')).open('w', encoding='utf-8')
        self.command = [sys.executable, str(HERE / 'receiver.py'), '--root', str(root / 'receiver'), '--instance', instance]
        self.process = subprocess.Popen(self.command, stdout=self.out, stderr=self.err)
        deadline = time.monotonic() + 10
        ready = root / 'receiver' / ('ready-' + instance + '.json')
        while not ready.exists():
            if self.process.poll() is not None or time.monotonic() > deadline:
                self.close()
                raise RuntimeError('Receiver startup failed')
            time.sleep(.01)
        self.url = json.loads(ready.read_text())['url']

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=10)
        self.out.close()
        self.err.close()
        write_json(self.root / (self.instance + '.process.json'), {'command': self.command,
                   'exit': self.process.returncode, 'instance': self.instance})


def run_case(output, case, repetition):
    run_id = f'{case}-r{repetition}-{uuid.uuid4().hex[:8]}'
    root = output / run_id
    root.mkdir()
    operation_a, operation_b = run_id + '-opA', run_id + '-opB'
    key_a, key_b = run_id + '-keyA', run_id + '-keyB'
    payload = {'account': 'synthetic-account', 'amount_cents': 2500}
    distinct = case in ('distinct_intents_distinct_keys', 'distinct_intents_reused_key')
    plan = {'run_id': run_id, 'case': case, 'repetition': repetition,
            'intents': [{'operation_id': operation_a, 'payload': payload, 'key': key_a}] +
                       ([{'operation_id': operation_b, 'payload': payload, 'key': key_b}] if distinct else []),
            'expected_business_effects': 2 if distinct else 1,
            'fixture_origin': 'independent deterministic synthetic intent plan'}
    write_json(root / 'intent-plan.json', plan)
    receiver = Receiver(root, 'receiver-1')
    db = root / 'receiver/ledger.sqlite'
    result = {'run_id': run_id, 'case': case, 'repetition': repetition, 'started_at': utc(),
              'plan': plan, 'attempts': [], 'observations': [], 'receiver_restart': False}

    def observe(label):
        value = {'at': utc(), 'label': label, **snapshot(db)}
        write_json(root / ('state-' + label + '.json'), value)
        result['observations'].append(value)
        return value

    def attempt(number, key=key_a, operation_id=operation_a, body=payload, fault=None, barrier=None):
        request = {'attempt_id': run_id + '-attempt' + str(number), 'operation_id': operation_id,
                   'payload': body, 'scope': 'synthetic-tenant', 'key': key}
        if fault:
            request['fault'] = fault
            if fault.startswith('hold_'):
                request['gate'] = run_id + '-gate' + str(number)
        if barrier:
            request['barrier'] = barrier
        request_path = root / ('attempt-' + str(number) + '-request.json')
        write_json(request_path, request)
        response_path = root / ('attempt-' + str(number) + '-result.json')
        process = command_run([sys.executable, str(HERE / 'client.py'), '--url', receiver.url,
                              '--request', str(request_path), '--output', str(response_path)],
                              root, 'attempt-' + str(number))
        response = json.loads(response_path.read_text())
        assert process.returncode == response['client_exit']
        return response

    try:
        if case == 'control':
            result['attempts'].append(attempt(1))
        elif case.startswith('after_commit_') or case == 'before_commit_timeout':
            first_key = None if case == 'after_commit_no_key' else key_a
            second_key = key_b if case == 'after_commit_per_attempt_key' else first_key
            fault = 'hold_before_abort' if case == 'before_commit_timeout' else 'hold_after_commit'
            try:
                result['attempts'].append(attempt(1, key=first_key, fault=fault))
                observe('after-timeout-before-gate-release')
            finally:
                control(receiver.url, 'release', {'gate': run_id + '-gate1'})
            result['attempts'].append(attempt(2, key=second_key))
        elif case == 'payload_mismatch':
            result['attempts'].append(attempt(1))
            result['attempts'].append(attempt(2, body={**payload, 'amount_cents': 9999}))
        elif distinct:
            result['attempts'].append(attempt(1))
            result['attempts'].append(attempt(2, operation_id=operation_b,
                key=key_b if case == 'distinct_intents_distinct_keys' else key_a))
        elif case == 'concurrent_stable_key':
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as workers:
                pending = [workers.submit(attempt, number, barrier=run_id + '-concurrent') for number in (1, 2)]
                result['attempts'] = [future.result() for future in pending]
        elif case in ('crash_before_commit', 'crash_after_commit'):
            result['attempts'].append(attempt(1, fault=case))
            receiver.process.wait(timeout=10)
            result['injected_receiver_exit'] = receiver.process.returncode
            receiver.close()
            observe('after-crash-before-restart')
            receiver = Receiver(root, 'receiver-2')
            result['receiver_restart'] = True
            result['attempts'].append(attempt(2))
        elif case == 'dedup_record_removed':
            result['attempts'].append(attempt(1))
            observe('before-retention-removal')
            result['retention_action'] = control(receiver.url, 'forget', {'scope': 'synthetic-tenant', 'key': key_a})
            observe('after-retention-removal')
            result['attempts'].append(attempt(2))
        result['final_state'] = observe('final')
        result['receiver_events'] = [json.loads(line) for line in (root / 'receiver/events.jsonl').read_text().splitlines()]
        expected_rows = sorted((intent['operation_id'], intent['payload']['account'], intent['payload']['amount_cents']) for intent in plan['intents'])
        actual_rows = sorted((row['operation_id'], row['account'], row['amount_cents']) for row in result['final_state']['effects'])
        result['business_target_met'] = actual_rows == expected_rows
        result['ended_at'] = utc()
        write_json(root / 'result.json', result)
        return result
    finally:
        receiver.close()


def check(result):
    case = result['case']
    attempts = result['attempts']
    final = result['final_state']
    expected_count = 2 if case in ('after_commit_no_key', 'after_commit_per_attempt_key',
                                  'distinct_intents_distinct_keys', 'dedup_record_removed') else 1
    assert len(final['effects']) == expected_count, ('effect_count', case, final)
    assert final['integrity_rows'] == [['ok']] and final['foreign_key_rows'] == []
    assert result['business_target_met'] == (case not in ('after_commit_no_key', 'after_commit_per_attempt_key',
                                                        'distinct_intents_reused_key', 'dedup_record_removed'))
    if case.startswith('after_commit_') or case == 'before_commit_timeout':
        assert attempts[0]['error_type'] == 'TimeoutError', attempts[0]
        observed = result['observations'][0]
        assert len(observed['effects']) == (0 if case == 'before_commit_timeout' else 1)
        assert attempts[1]['status'] == 201
        events = attempts[0]['events']
        assert [e['event'] for e in events] == ['request_sent', 'test_gate_confirmed', 'response_read_started', 'client_error']
        gate = next(e for e in result['receiver_events'] if e['event'] == 'gate_reached')
        assert gate['stage'] == ('before_transaction' if case == 'before_commit_timeout' else 'after_commit')
        assert gate['at'] <= events[-1]['at'] <= observed['at']
        if case.startswith('after_commit_'):
            committed = next(e for e in result['receiver_events'] if e['event'] == 'transaction_committed')
            assert committed['at'] <= gate['at']
        if case == 'after_commit_stable_key':
            assert attempts[1]['replayed']
            assert attempts[1]['status'] == observed['dedup'][0]['status']
            assert attempts[1]['response_json'] == observed['dedup'][0]['response_json']
    elif case == 'payload_mismatch':
        assert [a['status'] for a in attempts] == [201, 409]
    elif case == 'concurrent_stable_key':
        assert [a['status'] for a in attempts] == [201, 201]
        assert sorted(a['replayed'] for a in attempts) == [False, True]
        assert attempts[0]['response_json'] == attempts[1]['response_json']
        names = [e['event'] for e in result['receiver_events']]
        first_commit = names.index('transaction_committed')
        assert names[:first_commit].count('concurrent_barrier_arrived') == 2
    elif case in ('crash_before_commit', 'crash_after_commit'):
        assert attempts[0]['error_type'] in ('RemoteDisconnected', 'ConnectionResetError'), attempts[0]
        assert result['injected_receiver_exit'] == (88 if case == 'crash_before_commit' else 89)
        observed = result['observations'][0]
        assert len(observed['effects']) == (0 if case == 'crash_before_commit' else 1)
        assert len(observed['dedup']) == (0 if case == 'crash_before_commit' else 1)
        assert attempts[1]['replayed'] == (case == 'crash_after_commit')
        if case == 'crash_after_commit':
            assert attempts[1]['status'] == observed['dedup'][0]['status']
            assert attempts[1]['response_json'] == observed['dedup'][0]['response_json']
    elif case == 'distinct_intents_reused_key':
        assert attempts[1]['replayed'] and attempts[0]['response_json'] == attempts[1]['response_json']
    elif case == 'dedup_record_removed':
        assert result['retention_action']['removed'] == 1
        assert not attempts[1]['replayed']
    # Exactly one new child process per attempt; no client memory is shared across retries.
    assert len({a['pid'] for a in attempts}) == len(attempts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('case', choices=['all'] + CASES)
    p.add_argument('--output', required=True)
    p.add_argument('--repetitions', type=int, default=3)
    args = p.parse_args()
    if args.repetitions < 1:
        p.error('repetitions must be positive')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'environment.json', {'started_at': utc(), 'python': sys.version,
        'sqlite': sqlite3.sqlite_version, 'platform': platform.platform(),
        'command': [sys.executable, *sys.argv], 'source_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(HERE.glob('*.py'))}, 'git_commit': None, 'synthetic_only': True})
    results, failures = [], []
    for repetition in range(1, args.repetitions + 1):
        for case in CASES if args.case == 'all' else [args.case]:
            result = run_case(output, case, repetition)
            try:
                check(result)
                result['expectation_passed'] = True
            except AssertionError as exc:
                result['expectation_passed'] = False
                result['assertion_error'] = str(exc)
                failures.append(result['run_id'])
            results.append(result)
            write_json(output / 'RESULTS.json', results)
            print(json.dumps({'case': case, 'repetition': repetition, 'effects': len(result['final_state']['effects']),
                'business_target_met': result['business_target_met'], 'expectation_passed': result['expectation_passed']}), flush=True)
    write_json(output / 'SUMMARY.json', {'completed_at': utc(), 'cases': len(results),
               'expectations_passed': len(results) - len(failures), 'failures': failures})
    environment = json.loads((output / 'environment.json').read_text())
    environment['observed_sqlite_settings'] = results[0]['final_state']['sqlite_settings']
    write_json(output / 'environment.json', environment)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
