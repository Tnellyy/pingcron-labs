import sqlite3
from pathlib import Path


def connect(path):
    con = sqlite3.connect(path, timeout=10, isolation_level=None)
    con.execute('PRAGMA synchronous=FULL')
    con.execute('PRAGMA foreign_keys=ON')
    return con


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = connect(path)
    try:
        con.execute('PRAGMA journal_mode=DELETE')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS effects(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          operation_id TEXT NOT NULL, account TEXT NOT NULL, amount_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS dedup(
          scope TEXT NOT NULL, operation_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
          status INTEGER NOT NULL, response_json TEXT NOT NULL,
          effect_id INTEGER NOT NULL REFERENCES effects(id),
          PRIMARY KEY(scope, operation_key));
        ''')
    finally:
        con.close()


def snapshot(path):
    con = connect(path)
    try:
        return {'effects': [dict(zip(('effect_id', 'operation_id', 'account', 'amount_cents'), row))
                            for row in con.execute('SELECT id,operation_id,account,amount_cents FROM effects ORDER BY id')],
                'dedup': [dict(zip(('scope', 'operation_key', 'fingerprint', 'status', 'response_json', 'effect_id'), row))
                          for row in con.execute('SELECT scope,operation_key,fingerprint,status,response_json,effect_id FROM dedup ORDER BY scope,operation_key')],
                'integrity_rows': [list(row) for row in con.execute('PRAGMA integrity_check')],
                'foreign_key_rows': [list(row) for row in con.execute('PRAGMA foreign_key_check')],
                'sqlite_settings': {'journal_mode': con.execute('PRAGMA journal_mode').fetchone()[0],
                                    'synchronous': con.execute('PRAGMA synchronous').fetchone()[0],
                                    'busy_timeout_ms': con.execute('PRAGMA busy_timeout').fetchone()[0],
                                    'foreign_keys': con.execute('PRAGMA foreign_keys').fetchone()[0]}}
    finally:
        con.close()
