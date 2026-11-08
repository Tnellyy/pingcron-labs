"""Create a new SQLite snapshot with the backup API, then package and rename."""
import argparse
import json
import os
import sqlite3
import sys
import zipfile
from pathlib import Path
from common import utc


def export(source, output, run_id):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = output.with_suffix('.snapshot.sqlite')
    temporary = output.with_suffix('.tmp')
    if any(p.exists() for p in (output, snapshot, temporary)):
        raise FileExistsError('Exporter refuses to overwrite an artifact')
    src = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    dst = sqlite3.connect(snapshot)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    metadata = {'run_id': run_id, 'created_at': utc(), 'configured_source': str(source)}
    with zipfile.ZipFile(temporary, 'x', zipfile.ZIP_STORED) as archive:
        archive.write(snapshot, 'backup.sqlite')
        archive.writestr('metadata.json', json.dumps(metadata))
    os.replace(temporary, output)
    print(json.dumps({'exported': str(output), 'metadata': metadata}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    try:
        export(args.source, args.output, args.run_id)
    except Exception as exc:
        print(json.dumps({'error': type(exc).__name__, 'detail': str(exc)}))
        sys.exit(2)
