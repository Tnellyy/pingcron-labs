"""Fresh-process verifier with an explicit, non-security audit guard."""
import argparse
import json
import sqlite3
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from common import digest, utc, write_json


def install_source_guard(sources, allowed_db):
    sources, allowed_db = Path(sources).resolve(), Path(allowed_db).resolve()

    def normalized(value):
        value = str(value)
        if value.startswith('file:'):
            value = urllib.request.url2pathname(urllib.parse.urlsplit(value).path)
        return Path(value).resolve()

    def guard(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes)):
            path = normalized(args[0])
            if path == sources or sources in path.parents:
                raise PermissionError('Lab guard denies original source files')
        elif event == 'sqlite3.connect':
            if normalized(args[0]) != allowed_db:
                raise PermissionError('Lab guard permits only downloaded restore database')

    sys.addaudithook(guard)


def verify(args):
    root = Path(args.root).resolve()
    restore = root / 'restore'
    restore.mkdir(exist_ok=False)
    database = restore / 'restored.sqlite'
    expected = json.loads((root / 'expected.json').read_text(encoding='utf-8'))
    result = {'at': utc(), 'run_id': args.run_id, 'download_status': None,
              'digest_matches': None, 'artifact_run_matches': None,
              'integrity_rows': None, 'foreign_key_rows': None,
              'semantic_match': None, 'actual': None, 'expected': expected,
              'source_read_probes': {}, 'guard': 'Python audit hook, not an OS security sandbox'}
    install_source_guard(root / 'sources', database)
    for name, action in {
        'python_open': lambda: (root / 'sources' / 'intended.sqlite').read_bytes(),
        'sqlite_connect': lambda: sqlite3.connect((root / 'sources' / 'intended.sqlite').as_uri() + '?mode=ro', uri=True),
    }.items():
        try:
            leaked = action()
            if hasattr(leaked, 'close'):
                leaked.close()
            result['source_read_probes'][name] = 'UNEXPECTED_ACCESS'
        except PermissionError:
            result['source_read_probes'][name] = 'denied'
    try:
        with urllib.request.urlopen(args.url, timeout=10) as response:
            result['download_status'] = response.status
            data = response.read()
        downloaded = restore / 'downloaded.zip'
        downloaded.write_bytes(data)
        result['downloaded_sha256'] = digest(data)
        result['expected_sha256'] = args.sha256
        result['digest_matches'] = digest(data) == args.sha256
        if not result['digest_matches']:
            raise ValueError('Retrieved bytes do not match uploaded bytes')
        with zipfile.ZipFile(downloaded) as archive:
            # Explicit names, never extract arbitrary archive paths.
            database.write_bytes(archive.read('backup.sqlite'))
            metadata = json.loads(archive.read('metadata.json'))
        result['artifact_metadata'] = metadata
        result['artifact_run_matches'] = metadata['run_id'] == args.run_id
        con = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
        try:
            result['integrity_rows'] = [list(row) for row in con.execute('PRAGMA integrity_check')]
            result['foreign_key_rows'] = [list(row) for row in con.execute('PRAGMA foreign_key_check')]
            actual = {
                'accounts': [list(row) for row in con.execute('SELECT id,name FROM accounts ORDER BY id')],
                'entries': [list(row) for row in con.execute('SELECT transaction_id,account_id,amount_cents FROM entries ORDER BY transaction_id')],
            }
            actual['expected_transaction_present'] = any(row[0] == expected['expected_transaction'] for row in actual['entries'])
            actual['latest_transaction'] = max((row[0] for row in actual['entries']), default=None)
            result['actual'] = actual
            result['semantic_match'] = (actual['accounts'] == expected['accounts'] and
                actual['entries'] == expected['entries'] and actual['expected_transaction_present'])
        finally:
            con.close()
        passed = (result['integrity_rows'] == [['ok']] and result['foreign_key_rows'] == []
                  and result['semantic_match'] and result['artifact_run_matches']
                  and all(v == 'denied' for v in result['source_read_probes'].values()))
        result['passed'] = bool(passed)
    except Exception as exc:
        result['passed'] = False
        result['error'] = {'type': type(exc).__name__, 'detail': str(exc)}
        if hasattr(exc, 'code'):
            result['download_status'] = exc.code
    write_json(root / 'verification.json', result)
    write_json(root / 'logical-diff.json', {'expected': expected, 'actual': result['actual'],
               'semantic_match': result['semantic_match']})
    print(json.dumps(result))
    return 0 if result['passed'] else 3


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--url', required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--run-id', required=True)
    sys.exit(verify(p.parse_args()))
