"""One run; deliberately weak comparator and validated policy share evidence."""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from common import digest, utc, write_json

HERE = Path(__file__).resolve().parent


def child(command, root, label):
    start = utc()
    clock = time.monotonic()
    run = subprocess.run(command, capture_output=True, text=True, timeout=30)
    (root / (label + '.stdout.txt')).write_text(run.stdout, encoding='utf-8')
    (root / (label + '.stderr.txt')).write_text(run.stderr, encoding='utf-8')
    write_json(root / (label + '.process.json'), {'command': command, 'started_at': start,
               'ended_at': utc(), 'elapsed_seconds': time.monotonic() - clock, 'exit': run.returncode})
    return run


def checkin(base, run_id, policy):
    request = urllib.request.Request(base + '/checkin',
        data=json.dumps({'run_id': run_id, 'policy': policy}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {'status': 'received', 'http_status': response.status, 'at': utc()}
    except Exception as exc:
        return {'status': 'failed', 'http_status': getattr(exc, 'code', None), 'at': utc(), 'detail': str(exc)}


def run(args):
    root = Path(args.root).resolve()
    source = root / 'sources' / ('stale.sqlite' if args.case == 'wrong_source' else 'intended.sqlite')
    if args.case == 'masked_export_failure':
        source = root / 'sources' / 'missing.sqlite'
    artifact = root / 'artifacts' / (args.run_id + '.zip')
    result = {'run_id': args.run_id, 'case': args.case, 'started_at': utc(),
              'configured_source': str(source), 'exporter_exit': None, 'validator_exit': None,
              'weak_wrapper_exit': None, 'wrapper_exit': None, 'upload_status': None,
              'weak_checkin': {'status': 'not_attempted'}, 'validated_checkin': {'status': 'not_attempted'}}
    export_command = [sys.executable, str(HERE / 'backup.py'), '--source', str(source),
                      '--output', str(artifact), '--run-id', args.run_id]
    if args.case == 'masked_export_failure':
        weak = child([sys.executable, str(HERE / 'weak_wrapper.py'), '--root', str(root), '--',
                      *export_command], root, 'weak_masking_wrapper')
        result['weak_wrapper_exit'] = weak.returncode
        exporter_exit = json.loads((root / 'exporter.process.json').read_text())['exit']
    else:
        exported = child(export_command, root, 'exporter')
        exporter_exit = exported.returncode
    result['exporter_exit'] = exporter_exit
    selected = artifact
    if args.case == 'stale_artifact':
        # Deliberate selector bug: the current export succeeded, but an older artifact is uploaded.
        selected = root / 'artifacts' / 'previous.zip'
        prior = child([sys.executable, str(HERE / 'backup.py'), '--source', str(root / 'sources' / 'stale.sqlite'),
                       '--output', str(selected), '--run-id', args.run_id + '-previous'], root, 'prior_artifact_setup')
        if prior.returncode:
            raise RuntimeError('Could not set up stale artifact comparator')
    if exporter_exit == 0:
        data = selected.read_bytes()
        result['selected_artifact'] = str(selected)
        result['uploaded_sha256'] = digest(data)
        url = args.receiver + '/objects/' + args.run_id + '.zip'
        request = urllib.request.Request(url, data=data, method='PUT')
        with urllib.request.urlopen(request, timeout=10) as response:
            result['upload_status'] = response.status
            result['upload_ack'] = json.loads(response.read())
        result['weak_wrapper_exit'] = 0
        result['weak_checkin'] = checkin(args.receiver, args.run_id, 'weak_exit_upload_only')
        verified = child([sys.executable, str(HERE / 'verify_restore.py'), '--root', str(root),
                          '--url', url, '--sha256', digest(data), '--run-id', args.run_id], root, 'validator')
        result['validator_exit'] = verified.returncode
        result['wrapper_exit'] = 0 if verified.returncode == 0 else 1
        if verified.returncode == 0:
            result['validated_checkin'] = checkin(args.receiver, args.run_id, 'validated')
    else:
        # Real weak wrapper child exits 0 although the exporter failed. It is explicitly a bug.
        if args.case == 'masked_export_failure':
            result['weak_checkin'] = checkin(args.receiver, args.run_id, 'weak_masked_failure')
        else:
            result['weak_wrapper_exit'] = exporter_exit
        result['wrapper_exit'] = 1
    result['ended_at'] = utc()
    write_json(root / 'result.json', result)
    print(json.dumps(result))
    return result['wrapper_exit']


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--case', required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--receiver', required=True)
    sys.exit(run(p.parse_args()))
