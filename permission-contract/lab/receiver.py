"""Toy HTTP policy contract, not MCP/OAuth. All keys are public synthetic fixtures."""
import argparse
import json
import os
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def connect(path):
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA synchronous=FULL')
    return db


def initialize(path):
    db = connect(path)
    try:
        db.executescript('''
        CREATE TABLE credentials(credential TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                                 can_read INTEGER NOT NULL, can_write INTEGER NOT NULL);
        INSERT INTO credentials VALUES('synthetic-reader-A','tenant-A',1,0);
        INSERT INTO credentials VALUES('synthetic-broad-A','tenant-A',1,1);
        CREATE TABLE resources(id TEXT PRIMARY KEY, tenant TEXT NOT NULL, value TEXT NOT NULL,
                               version INTEGER NOT NULL);
        INSERT INTO resources VALUES('resource-A','tenant-A','A-private-fixture',0);
        INSERT INTO resources VALUES('resource-B','tenant-B','B-private-fixture',0);
        CREATE TABLE mutations(id INTEGER PRIMARY KEY, resource TEXT, old_value TEXT, new_value TEXT);
        CREATE TABLE audit(id INTEGER PRIMARY KEY, action TEXT, resource TEXT, decision TEXT);
        ''')
    finally:
        db.close()


def dispatch(path, credential, request):
    db = connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        policy = db.execute('SELECT * FROM credentials WHERE credential=?', (credential,)).fetchone()
        action = request['action']
        resource_id = request['resource']
        status, body, decision = 200, {}, 'allowed'
        if policy is None:
            status, body, decision = 401, {'error': 'unauthorized'}, 'unknown_credential'
        elif not policy['can_' + action]:
            status, body, decision = 403, {'error': 'forbidden'}, 'scope_denied'
        else:
            resource = db.execute('SELECT * FROM resources WHERE id=? AND tenant=?',
                                  (resource_id, policy['tenant'])).fetchone()
            if resource is None:
                status, body, decision = 403, {'error': 'forbidden'}, 'resource_denied'
            elif action == 'read':
                body = {'resource': resource_id, 'value': resource['value'], 'version': resource['version']}
            else:
                db.execute('UPDATE resources SET value=?,version=version+1 WHERE id=? AND tenant=?',
                           (request['value'], resource_id, policy['tenant']))
                db.execute('INSERT INTO mutations(resource,old_value,new_value) VALUES(?,?,?)',
                           (resource_id, resource['value'], request['value']))
                body = {'resource': resource_id, 'value': request['value'], 'version': resource['version'] + 1}
        db.execute('INSERT INTO audit(action,resource,decision) VALUES(?,?,?)', (action, resource_id, decision))
        db.commit()
        return status, body
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--ready', required=True)
    args = parser.parse_args()
    initialize(args.db)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != '/call':
                self.send_error(404)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096:
                    raise ValueError('request size')
                request = json.loads(self.rfile.read(size))
                if not isinstance(request, dict) or request.get('action') not in ('read', 'write'):
                    raise ValueError('action')
                if not isinstance(request.get('resource'), str):
                    raise ValueError('resource')
                if request['action'] == 'write' and not isinstance(request.get('value'), str):
                    raise ValueError('value')
                authorization = self.headers.get('Authorization', '')
                credential = authorization[7:] if authorization.startswith('Bearer ') else ''
                status, body = dispatch(args.db, credential, request)
            except (ValueError, TypeError, json.JSONDecodeError):
                status, body = 400, {'error': 'invalid_request'}
            payload = json.dumps(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            print(json.dumps({'status': status, 'body': body}), flush=True)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Path(args.ready).write_text(json.dumps({'pid': os.getpid(), 'port': server.server_port}), encoding='utf-8')
    def stop():
        if sys.stdin.readline().strip() == 'stop':
            server.shutdown()
    threading.Thread(target=stop, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
