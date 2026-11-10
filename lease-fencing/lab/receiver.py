"""Cooperative loopback receiver. Fence and business mutation share one transaction."""
import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from common import connect, dump_json


def initialize(path):
    db = connect(path)
    try:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS resources(resource TEXT PRIMARY KEY,
          value TEXT NOT NULL, highest_token INTEGER NOT NULL);
        INSERT OR IGNORE INTO resources VALUES('report','initial',0);
        CREATE TABLE IF NOT EXISTS mutations(id INTEGER PRIMARY KEY,
          resource TEXT, owner TEXT, token INTEGER, value TEXT, accepted_ns INTEGER);
        CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,
          owner TEXT, token INTEGER, value TEXT, decision TEXT, observed_highest INTEGER,
          observed_ns INTEGER);
        ''')
    finally:
        db.close()


def mutate(path, policy, request):
    db = connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        current = dict(db.execute("SELECT * FROM resources WHERE resource='report'").fetchone())
        now = time.monotonic_ns()
        token = request['token']
        denied = policy == 'fenced' and token < current['highest_token']
        decision = 'rejected_stale' if denied else 'accepted'
        db.execute('INSERT INTO attempts(owner,token,value,decision,observed_highest,observed_ns) VALUES(?,?,?,?,?,?)',
                   (request['owner'], token, request['value'], decision, current['highest_token'], now))
        if not denied:
            db.execute("UPDATE resources SET value=?,highest_token=? WHERE resource='report'",
                       (request['value'], max(token, current['highest_token'])))
            db.execute('INSERT INTO mutations(resource,owner,token,value,accepted_ns) VALUES(?,?,?,?,?)',
                       ('report', request['owner'], token, request['value'], now))
        result = dict(db.execute("SELECT * FROM resources WHERE resource='report'").fetchone())
        db.commit()
        return (409 if denied else 200), {'decision': decision, 'state': result}
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--ready', required=True)
    parser.add_argument('--policy', choices=['fenced', 'unguarded'], required=True)
    args = parser.parse_args()
    initialize(args.db)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != '/write':
                self.send_error(404)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096:
                    raise ValueError('invalid request size')
                request = json.loads(self.rfile.read(size))
                if (set(request) != {'owner', 'token', 'value'}
                        or type(request['token']) is not int or request['token'] < 1
                        or not isinstance(request['owner'], str) or not isinstance(request['value'], str)):
                    raise ValueError('invalid synthetic request')
                status, response = mutate(args.db, args.policy, request)
            except (ValueError, TypeError, json.JSONDecodeError):
                self.send_error(400)
                return
            payload = json.dumps(response).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            print(json.dumps({'event': 'write_response', 'pid': os.getpid(), 'status': status,
                              'request': request, 'response': response, 'monotonic_ns': time.monotonic_ns()}), flush=True)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    dump_json(args.ready, {'pid': os.getpid(), 'port': server.server_port, 'policy': args.policy,
                          'monotonic_ns': time.monotonic_ns()})
    def stop_on_stdin():
        if sys.stdin.readline().strip() == 'stop':
            server.shutdown()
    threading.Thread(target=stop_on_stdin, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
