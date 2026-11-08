"""One fresh client process per attempt, with explicit test-only gate synchronization."""
import argparse
import http.client
import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from common import utc, write_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', required=True)
    p.add_argument('--request', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    request = json.loads(Path(args.request).read_text())
    target = urllib.parse.urlsplit(args.url)
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=10)
    result = {'attempt_id': request['attempt_id'], 'operation_id': request['operation_id'],
              'pid': os.getpid(), 'request': request, 'events': [], 'status': None,
              'error_type': None, 'response_json': None, 'replayed': None}
    def event(name, **values):
        result['events'].append({'at': utc(), 'event': name, **values})
    try:
        connection.request('POST', '/effect', body=json.dumps(request).encode(), headers={'Content-Type': 'application/json'})
        event('request_sent')
        if request.get('gate'):
            deadline = time.monotonic() + 10
            while True:
                with urllib.request.urlopen(args.url + '/control/state', timeout=3) as response:
                    state = json.loads(response.read())['gates'].get(request['gate'])
                if state and state['stage']:
                    event('test_gate_confirmed', stage=state['stage'])
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('Test gate not reached')
                time.sleep(.01)
            connection.sock.settimeout(.2)
            event('response_read_started', injected_timeout_seconds=.2)
        else:
            event('response_read_started', injected_timeout_seconds=None)
        response = connection.getresponse()
        result['status'] = response.status
        result['replayed'] = response.getheader('X-Replayed') == 'true'
        result['response_json'] = response.read().decode()
        event('response_received', status=response.status)
        code = 0 if response.status < 400 else 4
    except Exception as exc:
        result['error_type'] = type(exc).__name__
        result['error_detail'] = str(exc)
        event('client_error', error_type=type(exc).__name__)
        code = 5 if isinstance(exc, (TimeoutError, socket.timeout)) else 6
    finally:
        connection.close()
    result['client_exit'] = code
    write_json(args.output, result)
    print(json.dumps(result))
    return code


if __name__ == '__main__':
    sys.exit(main())
