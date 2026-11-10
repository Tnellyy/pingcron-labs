"""Local synthetic lease authority and shared JSON/SQLite helpers."""
import json
import sqlite3
import time
from pathlib import Path


def connect(path):
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('PRAGMA busy_timeout=10000')
    return db


def initialize_authority(path):
    db = connect(path)
    try:
        db.executescript('''
        CREATE TABLE lease(resource TEXT PRIMARY KEY, owner TEXT, token INTEGER NOT NULL,
                           granted_ns INTEGER NOT NULL, expires_ns INTEGER NOT NULL);
        INSERT INTO lease VALUES('report', NULL, 0, 0, 0);
        CREATE TABLE grants(id INTEGER PRIMARY KEY, owner TEXT, token INTEGER,
                            granted_ns INTEGER, expires_ns INTEGER);
        ''')
    finally:
        db.close()


def acquire(path, owner, ttl_ms):
    db = connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        now = time.monotonic_ns()
        row = dict(db.execute("SELECT * FROM lease WHERE resource='report'").fetchone())
        if row['owner'] is not None and now < row['expires_ns']:
            db.rollback()
            return {'granted': False, 'observed_ns': now, 'current': row}
        token = row['token'] + 1
        expires = now + int(ttl_ms * 1_000_000)
        db.execute("UPDATE lease SET owner=?,token=?,granted_ns=?,expires_ns=? WHERE resource='report'",
                   (owner, token, now, expires))
        db.execute('INSERT INTO grants(owner,token,granted_ns,expires_ns) VALUES(?,?,?,?)',
                   (owner, token, now, expires))
        db.commit()
        return {'granted': True, 'owner': owner, 'token': token,
                'granted_ns': now, 'expires_ns': expires}
    finally:
        db.close()


def check_owner(path, owner, token):
    db = connect(path)
    try:
        row = dict(db.execute("SELECT * FROM lease WHERE resource='report'").fetchone())
        now = time.monotonic_ns()
        return {'owns': row['owner'] == owner and row['token'] == token and now < row['expires_ns'],
                'observed_ns': now, 'current': row}
    finally:
        db.close()


def dump_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def read_resource(path):
    db = connect(path)
    try:
        return {'resource': dict(db.execute("SELECT * FROM resources WHERE resource='report'").fetchone()),
                'mutations': [dict(r) for r in db.execute('SELECT * FROM mutations ORDER BY id')],
                'attempts': [dict(r) for r in db.execute('SELECT * FROM attempts ORDER BY id')]}
    finally:
        db.close()
