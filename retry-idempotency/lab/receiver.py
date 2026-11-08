"""Atomic synthetic local receiver. Control routes are fault-injection scaffolding."""
import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from common import fingerprint, utc, write_json
from ledger import connect, initialize


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--instance', required=True)
    args = p.parse_args()
    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    db = root / 'ledger.sqlite'
    initialize(db)
    event_lock, gate_lock = threading.Lock(), threading.Lock()
    gates, barriers = {}, {}

    def event(name, **values):
        with event_lock, (root / 'events.jsonl').open('a', encoding='utf-8') as output:
            output.write(json.dumps({'at': utc(), 'instance': args.instance, 'pid': os.getpid(),
                                     'event': name, **values}) + '\n')

    def hold(name, stage, attempt_id):
        with gate_lock:
            gate = gates.setdefault(name, {'release': threading.Event(), 'stage': None, 'finished': False})
            gate['stage'] = stage
        event('gate_reached', gate=name, stage=stage, attempt_id=attempt_id)
        if not gate['release'].wait(timeout=20):
            event('gate_safety_timeout', gate=name, attempt_id=attempt_id)
            raise TimeoutError('Harness did not release fault gate')
        event('gate_released', gate=name, attempt_id=attempt_id)
        with gate_lock:
            gate['finished'] = True

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, body, replayed=False):
            data = body.encode() if isinstance(body, str) else json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
            try:
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('X-Replayed', str(replayed).lower())
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as exc:
                event('response_write_failed', error=type(exc).__name__)

        def do_GET(self):
            if self.path != '/control/state':
                self.reply(404, {})
                return
            with gate_lock:
                state = {key: {'stage': value['stage'], 'finished': value['finished']}
                         for key, value in gates.items()}
            self.reply(200, {'gates': state})

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
            if self.path == '/control/release':
                with gate_lock:
                    gate = gates.get(request['gate'])
                    if gate:
                        gate['release'].set()
                self.reply(200 if gate else 404, {'released': bool(gate)})
                return
            if self.path == '/control/forget':
                con = connect(db)
                try:
                    con.execute('BEGIN IMMEDIATE')
                    changed = con.execute('DELETE FROM dedup WHERE scope=? AND operation_key=?',
                                          (request['scope'], request['key'])).rowcount
                    con.commit()
                finally:
                    con.close()
                event('test_retention_record_removed', scope=request['scope'], key=request['key'], rows=changed)
                self.reply(200, {'removed': changed})
                return
            if self.path != '/effect':
                self.reply(404, {})
                return
            attempt = request['attempt_id']
            operation = request['operation_id']
            payload = request['payload']
            if set(payload) != {'account', 'amount_cents'} or not isinstance(payload['account'], str) or type(payload['amount_cents']) is not int:
                self.reply(400, {'error': 'invalid_business_payload'})
                return
            scope, key = request.get('scope', 'synthetic-tenant'), request.get('key')
            fault, gate_name = request.get('fault'), request.get('gate')
            event('request_received', attempt_id=attempt, operation_id=operation, scope=scope, key=key,
                  fingerprint=fingerprint(payload), fault=fault)
            if request.get('barrier'):
                name = request['barrier']
                with gate_lock:
                    barrier = barriers.setdefault(name, threading.Barrier(2))
                event('concurrent_barrier_arrived', barrier=name, attempt_id=attempt)
                barrier.wait(timeout=10)
                event('concurrent_barrier_passed', barrier=name, attempt_id=attempt)
            if fault == 'hold_before_abort':
                hold(gate_name, 'before_transaction', attempt)
                event('request_aborted_before_transaction', attempt_id=attempt)
                self.close_connection = True
                return
            con = connect(db)
            replayed = False
            try:
                con.execute('BEGIN IMMEDIATE')
                record = con.execute('SELECT fingerprint,status,response_json FROM dedup WHERE scope=? AND operation_key=?', (scope, key)).fetchone() if key else None
                if record:
                    if record[0] != fingerprint(payload):
                        con.rollback()
                        event('payload_conflict', attempt_id=attempt, key=key)
                        self.reply(409, {'error': 'key_payload_mismatch'})
                        return
                    status, response = record[1], record[2]
                    replayed = True
                else:
                    effect_id = con.execute('INSERT INTO effects(operation_id,account,amount_cents) VALUES(?,?,?)',
                        (operation, payload['account'], payload['amount_cents'])).lastrowid
                    if fault == 'crash_before_commit':
                        event('crash_after_effect_insert_before_commit', attempt_id=attempt, uncommitted_effect_id=effect_id)
                        os._exit(88)
                    status = 201
                    response = json.dumps({'effect_id': effect_id, **payload}, sort_keys=True, separators=(',', ':'))
                    if key:
                        con.execute('INSERT INTO dedup VALUES(?,?,?,?,?,?)',
                            (scope, key, fingerprint(payload), status, response, effect_id))
                con.commit()
                event('transaction_committed', attempt_id=attempt, operation_id=operation, replayed=replayed,
                      response_json=response, status=status)
            except Exception as exc:
                con.rollback()
                event('transaction_error', attempt_id=attempt, error=type(exc).__name__, detail=str(exc))
                self.reply(500, {'error': type(exc).__name__})
                return
            finally:
                con.close()
            if fault == 'crash_after_commit':
                event('crash_after_commit_before_response', attempt_id=attempt)
                os._exit(89)
            if fault == 'hold_after_commit':
                hold(gate_name, 'after_commit', attempt)
            event('response_attempt', attempt_id=attempt, status=status, replayed=replayed)
            self.reply(status, response, replayed)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    write_json(root / ('ready-' + args.instance + '.json'), {'url': 'http://127.0.0.1:' + str(server.server_port),
               'pid': os.getpid(), 'instance': args.instance})
    event('receiver_ready')
    server.serve_forever()


if __name__ == '__main__':
    main()
