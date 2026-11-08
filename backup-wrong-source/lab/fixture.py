"""The specification is the independent oracle; never infer it from a backup."""
import sqlite3
from pathlib import Path
from common import write_json


def specification(marker):
    return {'accounts': [[1, 'production']],
            'entries': [[marker - 1, 1, 1200], [marker, 1, 4500]],
            'expected_transaction': marker}


def create_db(path, spec):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.executescript('''PRAGMA foreign_keys=ON;
        CREATE TABLE accounts(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE entries(transaction_id INTEGER PRIMARY KEY,
          account_id INTEGER NOT NULL REFERENCES accounts(id), amount_cents INTEGER NOT NULL);''')
        con.executemany('INSERT INTO accounts VALUES(?,?)', spec['accounts'])
        con.executemany('INSERT INTO entries VALUES(?,?,?)', spec['entries'])
    con.close()


def build(root, marker):
    root = Path(root)
    expected = specification(marker)
    # Oracle is written before, and independently of, either SQLite database.
    write_json(root / 'expected.json', expected)
    create_db(root / 'sources' / 'intended.sqlite', expected)
    stale = {**expected, 'entries': expected['entries'][:-1]}
    create_db(root / 'sources' / 'stale.sqlite', stale)
    write_json(root / 'fixture-specification.json', {'intended': expected, 'stale': stale,
               'writes_paused': True, 'origin': 'deterministic synthetic fixture'})
    return expected
