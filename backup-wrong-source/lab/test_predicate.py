"""Negative controls: unchanged counts and intact SQLite do not imply correct data."""
import json
import sqlite3
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from common import digest
from fixture import build
from receiver import object_key

HERE = Path(__file__).resolve().parent


class PredicateTests(unittest.TestCase):
    def execute(self, sql=None):
        root = HERE / 'test-results' / (self._testMethodName + '-' + uuid.uuid4().hex[:8])
        root.mkdir(parents=True)
        if root.exists():
            expected = build(root, 1042)
            source = root / 'sources' / 'intended.sqlite'
            if sql:
                con = sqlite3.connect(source)
                try:
                    con.execute(sql)
                    con.commit()
                finally:
                    con.close()
            run_id = uuid.uuid4().hex
            artifact = root / 'artifact.zip'
            export = subprocess.run([sys.executable, str(HERE / 'backup.py'), '--source', str(source),
                                    '--output', str(artifact), '--run-id', run_id], capture_output=True, text=True)
            self.assertEqual(export.returncode, 0, export.stdout + export.stderr)
            verify = subprocess.run([sys.executable, str(HERE / 'verify_restore.py'), '--root', str(root),
                '--url', artifact.as_uri(), '--sha256', digest(artifact.read_bytes()), '--run-id', run_id],
                capture_output=True, text=True)
            return verify.returncode, json.loads((root / 'verification.json').read_text()), expected

    def test_control_passes_and_source_reads_are_denied(self):
        code, result, _ = self.execute()
        self.assertEqual(code, 0)
        self.assertTrue(result['passed'])
        self.assertEqual(result['source_read_probes'], {'python_open': 'denied', 'sqlite_connect': 'denied'})

    def test_same_row_count_and_marker_but_wrong_amount_rejected(self):
        code, result, expected = self.execute('UPDATE entries SET amount_cents=1 WHERE transaction_id=1042')
        self.assertEqual(code, 3)
        self.assertEqual(result['integrity_rows'], [['ok']])
        self.assertEqual(result['foreign_key_rows'], [])
        self.assertEqual(len(result['actual']['entries']), len(expected['entries']))
        self.assertTrue(result['actual']['expected_transaction_present'])
        self.assertFalse(result['semantic_match'])

    def test_foreign_key_violation_is_not_an_integrity_check_failure(self):
        code, result, _ = self.execute('UPDATE entries SET account_id=999 WHERE transaction_id=1042')
        self.assertEqual(code, 3)
        self.assertEqual(result['integrity_rows'], [['ok']])
        self.assertEqual(len(result['foreign_key_rows']), 1)
        self.assertEqual(result['foreign_key_rows'][0][:3], ['entries', 1042, 'accounts'])
        self.assertFalse(result['passed'])

    def test_object_keys_cannot_escape_receiver_storage(self):
        self.assertEqual(object_key('/objects/wrong_source-r1-abcd.zip'), 'wrong_source-r1-abcd.zip')
        for path in ['/objects/../secret.zip', '/objects/..\\secret.zip', '/objects/C:\\secret.zip',
                     '/objects/%2e%2e%2fsecret.zip', '/not-objects/a.zip', '/objects/a.zip?x=1']:
            self.assertIsNone(object_key(path), path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
