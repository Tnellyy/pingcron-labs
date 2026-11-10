"""Reproduce eight bounded lease/fencing cases and inspect durable SQL evidence."""
import argparse
import csv
import hashlib
import json
import os
import platform
import queue
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from common import connect, dump_json, initialize_authority, read_resource

HERE = Path(__file__).resolve().parent
# Independent fixture expectations, not derived from the receiver response.
EXPECTED = {
    'control_fenced': {'value': 'A-control', 'payloads': ['A-control'], 'statuses': [200], 'highest': 1},
    'stale_unguarded': {'value': 'A-old', 'payloads': ['B-new', 'A-old'], 'statuses': [200, 200], 'highest': 2},
    'stale_fenced': {'value': 'B-new', 'payloads': ['B-new'], 'statuses': [200, 409], 'highest': 2},
    'owner_check_toctou': {'value': 'A-old', 'payloads': ['B-new', 'A-old'], 'statuses': [200, 200], 'highest': 2},
    'restart_fenced': {'value': 'B-new', 'payloads': ['B-new'], 'statuses': [200, 409], 'highest': 2},
    'unseen_successor': {'value': 'B-new', 'payloads': ['A-old', 'B-new'], 'statuses': [200, 200], 'highest': 2},
    'equal_token_writes': {'value': 'A-v2', 'payloads': ['A-v1', 'A-v2', 'A-v2'], 'statuses': [200, 200, 200], 'highest': 1},
    'token_counter_reset': {'value': 'B-new', 'payloads': ['B-new'], 'statuses': [200, 409], 'highest': 2},
}


class Worker:
    def __init__(self, directory, authority, owner, records):
        self.owner = owner
        self.records = records
        self.command = [sys.executable, '-u', str(HERE / 'worker.py'), '--authority', str(authority), '--owner', owner]
        self.stderr = open(directory / (owner + '-stderr.txt'), 'w', encoding='utf-8')
        self.raw = open(directory / (owner + '-stdout.jsonl'), 'w', encoding='utf-8')
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.stderr, text=True, encoding='utf-8', bufsize=1)
        self.lines = queue.Queue()
        def pump():
            for line in self.process.stdout:
                self.raw.write(line)
                self.raw.flush()
                self.lines.put(line)
            self.lines.put(None)
        self.thread = threading.Thread(target=pump, daemon=True)
        self.thread.start()
        self.ready = self.receive()
        if self.ready['event'] != 'ready':
            raise AssertionError('worker did not become ready')

    def receive(self):
        line = self.lines.get(timeout=15)
        if line is None:
            raise RuntimeError('worker exited before response')
        return json.loads(line)

    def send(self, **command):
        sent = time.monotonic_ns()
        self.process.stdin.write(json.dumps(command) + '\n')
        self.process.stdin.flush()
        reply = self.receive()
        self.records.append({'kind': 'worker_command', 'owner': self.owner, 'sent_ns': sent,
                             'command': command, 'reply': reply})
        return reply['result'] if 'result' in reply else reply

    def close(self):
        if self.process.poll() is None:
            self.send(action='stop')
        code = self.process.wait(timeout=10)
        self.thread.join(timeout=3)
        self.process.stdin.close()
        self.process.stdout.close()
        self.raw.close()
        self.stderr.close()
        return {'role': 'worker', 'owner': self.owner, 'pid': self.process.pid,
                'command': self.command, 'exit_code': code}


class Receiver:
    def __init__(self, directory, db, policy, number):
        stem = 'receiver-' + str(number)
        self.stdout = open(directory / (stem + '-stdout.jsonl'), 'w', encoding='utf-8')
        self.stderr = open(directory / (stem + '-stderr.txt'), 'w', encoding='utf-8')
        ready = directory / (stem + '-ready.json')
        self.command = [sys.executable, '-u', str(HERE / 'receiver.py'), '--db', str(db),
                        '--policy', policy, '--ready', str(ready)]
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=self.stdout,
                                        stderr=self.stderr, text=True, encoding='utf-8')
        deadline = time.monotonic() + 15
        while True:
            if self.process.poll() is not None:
                raise RuntimeError('receiver exited before ready')
            try:
                self.ready = json.loads(ready.read_text(encoding='utf-8'))
                break
            except (FileNotFoundError, json.JSONDecodeError):
                if time.monotonic() >= deadline:
                    raise TimeoutError('receiver readiness')
                threading.Event().wait(0.01)
        self.port = self.ready['port']

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.write('stop\n')
            self.process.stdin.flush()
        code = self.process.wait(timeout=10)
        self.process.stdin.close()
        self.stdout.close()
        self.stderr.close()
        return {'role': 'receiver', 'pid': self.process.pid, 'command': self.command, 'exit_code': code}


def run_case(root, name, repetition, lease_ms):
    run_id = '{}-r{}-{}'.format(name, repetition, uuid.uuid4().hex[:8])
    directory = root / run_id
    directory.mkdir()
    authority = directory / 'authority.sqlite'
    resource_db = directory / 'resource.sqlite'
    initialize_authority(authority)
    policy = 'unguarded' if name in ('stale_unguarded', 'owner_check_toctou') else 'fenced'
    expected = EXPECTED[name]
    dump_json(directory / 'intent.json', {'case': name, 'run_id': run_id, 'policy': policy,
                                          'expected': expected, 'short_lease_ms': lease_ms})
    records, checks, exits, statuses = [], [], [], []
    workers, receiver = [], None
    result = {'case': name, 'run_id': run_id, 'repetition': repetition, 'policy': policy,
              'expected': expected, 'checks': checks, 'events': records, 'processes': exits}
    def check(label, condition, evidence=None):
        checks.append({'label': label, 'passed': bool(condition), 'evidence': evidence})
        if not condition:
            raise AssertionError(label)
    def snapshot(label):
        value = read_resource(resource_db)
        records.append({'kind': 'sql_snapshot', 'label': label, 'monotonic_ns': time.monotonic_ns(), 'state': value})
        return value
    def write(worker, value):
        response = worker.send(action='write', port=receiver.port, value=value)
        statuses.append(response['status'])
        return response
    try:
        receiver = Receiver(directory, resource_db, policy, 1)
        a = Worker(directory, authority, 'A', records)
        workers.append(a)
        b = Worker(directory, authority, 'B', records)
        workers.append(b)
        long_case = name in ('control_fenced', 'equal_token_writes')
        grant_a = a.send(action='acquire', ttl_ms=30000 if long_case else lease_ms)
        check('A acquired first token', grant_a['granted'] and grant_a['token'] == 1, grant_a)
        result['grant_a'] = grant_a
        if name == 'control_fenced':
            denied = b.send(action='acquire', ttl_ms=30000)
            check('B refused while A lease unexpired', not denied['granted'] and denied['observed_ns'] < grant_a['expires_ns'], denied)
            write(a, 'A-control')
            control_state = snapshot('A-control')
            check('control write before expiry', control_state['mutations'][0]['accepted_ns'] < grant_a['expires_ns'])
        elif name == 'equal_token_writes':
            for value in expected['payloads']:
                write(a, value)
            state = snapshot('same-token-three-writes')
            check('three distinct mutation records share token 1',
                  len(state['mutations']) == 3 and {r['token'] for r in state['mutations']} == {1})
        else:
            if name == 'owner_check_toctou':
                preflight = a.send(action='check')
                result['preflight'] = preflight
                check('A ownership preflight really true', preflight['owns'], preflight)
            before_wait = time.monotonic_ns()
            while time.monotonic_ns() < grant_a['expires_ns']:
                remaining = (grant_a['expires_ns'] - time.monotonic_ns()) / 1e9
                if remaining > 0:
                    threading.Event().wait(remaining)
            expired_observed = time.monotonic_ns()
            result['expiry_observation'] = {'wait_started_ns': before_wait, 'observed_ns': expired_observed,
                                            'deadline_ns': grant_a['expires_ns'],
                                            'observed_past_deadline_ns': expired_observed - grant_a['expires_ns']}
            check('A process still alive after its actual deadline', a.process.poll() is None and expired_observed >= grant_a['expires_ns'])
            grant_b = b.send(action='acquire', ttl_ms=30000)
            result['grant_b'] = grant_b
            check('B grant occurs after A expires with larger token', grant_b['granted'] and grant_b['token'] == 2
                  and grant_b['granted_ns'] >= grant_a['expires_ns'], grant_b)
            if name == 'unseen_successor':
                first = write(a, 'A-old')
                state = snapshot('A-accepted-before-B-reaches-sink')
                check('expired A accepted before successor fence observed', first['status'] == 200
                      and state['resource']['value'] == 'A-old' and state['resource']['highest_token'] == 1)
                write(b, 'B-new')
            else:
                write(b, 'B-new')
                after_b = snapshot('after-B-write')
                check('B new value committed with fence 2', after_b['resource']['value'] == 'B-new'
                      and after_b['resource']['highest_token'] == 2)
                if name == 'restart_fenced':
                    old_pid = receiver.process.pid
                    exits.append(receiver.close())
                    receiver = Receiver(directory, resource_db, policy, 2)
                    check('new receiver process sees persisted state', receiver.process.pid != old_pid
                          and snapshot('after-receiver-restart') == after_b)
                writer = a
                if name == 'token_counter_reset':
                    db = connect(authority)
                    try:
                        db.execute('BEGIN IMMEDIATE')
                        db.execute("UPDATE lease SET owner=NULL,token=0,granted_ns=0,expires_ns=0 WHERE resource='report'")
                        db.commit()
                    finally:
                        db.close()
                    records.append({'kind': 'deliberate_authority_state_reset', 'monotonic_ns': time.monotonic_ns(), 'reset_token_to': 0})
                    c = Worker(directory, authority, 'C', records)
                    workers.append(c)
                    grant_c = c.send(action='acquire', ttl_ms=30000)
                    result['grant_c'] = grant_c
                    check('reset authority really grants fresh C token 1', grant_c['granted'] and grant_c['token'] == 1)
                    writer = c
                reply = write(writer, 'C-fresh' if name == 'token_counter_reset' else 'A-old')
                if policy == 'fenced':
                    after_reject = snapshot('after-rejected-write')
                    check('rejection preserves value fence and mutation history', reply['status'] == 409
                          and after_reject['resource'] == after_b['resource']
                          and after_reject['mutations'] == after_b['mutations'])
        observed = snapshot('final-before-shutdown')
        result['observed'] = observed
        result['statuses'] = statuses
        check('HTTP statuses match independent case plan', statuses == expected['statuses'], statuses)
        check('final business value matches independent case plan', observed['resource']['value'] == expected['value'], observed['resource'])
        check('mutation payload sequence matches independent case plan', [r['value'] for r in observed['mutations']] == expected['payloads'])
        check('durable high-water matches independent case plan', observed['resource']['highest_token'] == expected['highest'])
        check('one audit attempt per response', len(observed['attempts']) == len(statuses))
        if 'grant_b' in result:
            mutation_by_a = [r for r in observed['attempts'] if r['owner'] == 'A']
            if mutation_by_a:
                # GetTickCount64 may give causally ordered events identical timestamps.
                # The acknowledged command transcript establishes strict event order.
                b_grant_index = next(i for i, event in enumerate(records) if event.get('owner') == 'B'
                                     and event.get('command', {}).get('action') == 'acquire'
                                     and event['reply']['result']['granted'])
                a_write_index = next(i for i, event in enumerate(records) if event.get('owner') == 'A'
                                     and event.get('command', {}).get('action') == 'write')
                check('A really attempted write after expiry and B grant',
                      mutation_by_a[-1]['observed_ns'] >= result['grant_b']['granted_ns'] >= grant_a['expires_ns']
                      and a_write_index > b_grant_index,
                      {'B_grant_event_index': b_grant_index, 'A_write_event_index': a_write_index,
                       'A_attempt_ns': mutation_by_a[-1]['observed_ns'], 'B_grant_ns': result['grant_b']['granted_ns']})
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        for worker in workers:
            try:
                exits.append(worker.close())
            except Exception as error:
                worker.process.kill()
                worker.process.wait()
                exits.append({'role': 'worker', 'owner': worker.owner, 'cleanup_error': repr(error)})
        if receiver is not None:
            try:
                exits.append(receiver.close())
            except Exception as error:
                receiver.process.kill()
                receiver.process.wait()
                exits.append({'role': 'receiver', 'cleanup_error': repr(error)})
    final = read_resource(resource_db)
    result['durable_after_shutdown'] = final
    checks.append({'label': 'clean child process exits', 'passed': all(p.get('exit_code') == 0 for p in exits)})
    checks.append({'label': 'SQL state survives clean process shutdown', 'passed': final == result.get('observed')})
    result['passed'] = 'error' not in result and all(c['passed'] for c in checks)
    dump_json(directory / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='New directory; never overwrites existing evidence')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--lease-ms', type=int, default=500)
    parser.add_argument('--case', choices=list(EXPECTED))
    args = parser.parse_args()
    if args.repeats < 1 or args.lease_ms < 100:
        parser.error('positive repeats and lease >= 100ms required')
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))}
    db = connect(root / 'environment.sqlite')
    try:
        pragmas = {name: db.execute('PRAGMA ' + name).fetchone()[0] for name in ('journal_mode', 'synchronous', 'busy_timeout')}
    finally:
        db.close()
    env = {'utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version, 'executable': sys.executable,
           'platform': platform.platform(), 'sqlite': sqlite3.sqlite_version, 'sqlite_pragmas': pragmas,
           'monotonic_clock': vars(time.get_clock_info('monotonic')), 'command_argv': sys.argv,
           'source_sha256': hashes, 'pid': os.getpid(), 'cwd': os.getcwd(),
           'scope': 'single machine, synthetic SQLite effect, actual monotonic deadline, cooperative process gates'}
    dump_json(root / 'environment.json', env)
    results = []
    for name in ([args.case] if args.case else EXPECTED):
        for repetition in range(1, args.repeats + 1):
            result = run_case(root, name, repetition, args.lease_ms)
            results.append(result)
            print(json.dumps({'run_id': result['run_id'], 'passed': result['passed'], 'error': result.get('error')}), flush=True)
            dump_json(root / 'RESULTS.json', results)
    with open(root / 'RESULTS.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['case', 'run_id', 'repetition', 'policy', 'passed', 'value', 'highest_token', 'accepted_mutations', 'statuses', 'past_expiry_ns'])
        writer.writeheader()
        for result in results:
            observed = result.get('observed', {'resource': {}, 'mutations': []})
            writer.writerow({'case': result['case'], 'run_id': result['run_id'], 'repetition': result['repetition'],
                             'policy': result['policy'], 'passed': result['passed'],
                             'value': observed['resource'].get('value'), 'highest_token': observed['resource'].get('highest_token'),
                             'accepted_mutations': len(observed['mutations']), 'statuses': json.dumps(result.get('statuses')),
                             'past_expiry_ns': result.get('expiry_observation', {}).get('observed_past_deadline_ns')})
    summary = {'total': len(results), 'passed': sum(r['passed'] for r in results),
               'failed': sum(not r['passed'] for r in results), 'source_sha256': hashes,
               'meaning': 'Expected bounded observations reproduced, not success of every policy.'}
    dump_json(root / 'SUMMARY.json', summary)
    print(json.dumps(summary), flush=True)
    return 0 if summary['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
