"""Local simulated object store. Not a cloud durability test."""
import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from common import digest, utc, write_json


def object_key(path):
    if not path.startswith('/objects/'):
        return None
    key = path[len('/objects/'):]
    return key if re.fullmatch(r'[A-Za-z0-9_-]+\.zip', key) else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--mode', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def event(self, event, **kwargs):
            with lock, (root / 'events.jsonl').open('a', encoding='utf-8') as log:
                log.write(json.dumps({'at': utc(), 'event': event, **kwargs}) + '\n')

        def reply(self, code, data, content='application/json'):
            self.send_response(code)
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_PUT(self):
            key = object_key(self.path)
            if key is None:
                self.reply(400, b'{}')
                return
            data = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            received = digest(data)
            (root / key).write_bytes(data)
            self.event('upload_accepted', key=key, received_sha256=received, bytes=len(data))
            if args.mode == 'corrupt_transfer':
                mutated = bytearray(data)
                mutated[len(mutated) // 2] ^= 0x01
                (root / key).write_bytes(mutated)
                self.event('fault_mutated_stored_bytes', key=key)
            if args.mode == 'lost_object':
                (root / key).unlink()
                self.event('fault_removed_stored_object', key=key)
            self.reply(201, json.dumps({'key': key, 'received_sha256': received}).encode())

        def do_GET(self):
            key = object_key(self.path)
            if key is None:
                self.reply(400, b'{}')
                return
            path = root / key
            if not path.is_file():
                self.event('download_missing', key=key)
                self.reply(404, b'{}')
                return
            data = path.read_bytes()
            self.event('download', key=key, sha256=digest(data))
            self.reply(200, data, 'application/zip')

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            if self.path != '/checkin':
                self.reply(404, b'{}')
                return
            if args.mode == 'checkin_unavailable':
                self.event('checkin_rejected', **data)
                self.reply(503, b'{}')
                return
            self.event('checkin_received', **data)
            self.reply(200, b'{"received":true}')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    write_json(root / 'ready.json', {'url': 'http://127.0.0.1:' + str(server.server_port), 'pid': __import__('os').getpid()})
    server.serve_forever()


if __name__ == '__main__':
    main()
