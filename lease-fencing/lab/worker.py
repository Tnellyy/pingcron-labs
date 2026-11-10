"""Real worker process whose stdin commands form explicit scheduling gates."""
import argparse
import http.client
import json
import os
import sys
import time
from common import acquire, check_owner


def emit(value):
    print(json.dumps({'pid': os.getpid(), 'monotonic_ns': time.monotonic_ns(), **value}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authority', required=True)
    parser.add_argument('--owner', required=True)
    args = parser.parse_args()
    token = None
    emit({'event': 'ready', 'owner': args.owner})
    for line in sys.stdin:
        command = json.loads(line)
        action = command['action']
        if action == 'stop':
            emit({'event': 'stopped'})
            return
        if action == 'acquire':
            result = acquire(args.authority, args.owner, command['ttl_ms'])
            if result['granted']:
                token = result['token']
        elif action == 'check':
            result = check_owner(args.authority, args.owner, token)
        elif action == 'write':
            connection = http.client.HTTPConnection('127.0.0.1', command['port'], timeout=10)
            try:
                request = {'owner': args.owner, 'token': token, 'value': command['value']}
                connection.request('POST', '/write', json.dumps(request), {'Content-Type': 'application/json'})
                response = connection.getresponse()
                result = {'status': response.status, 'body': json.loads(response.read()), 'request': request}
            finally:
                connection.close()
        else:
            raise ValueError('unknown action')
        emit({'event': action, 'owner': args.owner, 'result': result})


if __name__ == '__main__':
    main()
