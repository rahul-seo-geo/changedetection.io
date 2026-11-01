import hashlib
import sqlite3
import time
from pathlib import Path


def connect(data_dir):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(Path(data_dir) / 'dealhound.sqlite3')
    db.execute('CREATE TABLE IF NOT EXISTS deals (hash TEXT PRIMARY KEY, link TEXT, title TEXT, price REAL, matched_item TEXT, ts REAL, judged INTEGER DEFAULT 0, alerted INTEGER DEFAULT 0)')
    try:
        db.execute('ALTER TABLE deals ADD COLUMN judged INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        db.execute('ALTER TABLE deals ADD COLUMN alerted INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    db.execute('CREATE TABLE IF NOT EXISTS feeds (url TEXT PRIMARY KEY, etag TEXT, modified TEXT, checked REAL)')
    db.execute('CREATE TABLE IF NOT EXISTS price_state (watch_uuid TEXT PRIMARY KEY, last_alerted REAL)')
    db.commit()
    return db


def insert(db, link, title, price, matched_item):
    digest = hashlib.sha1((link + '|' + title).encode('utf-8')).hexdigest()
    with db:
        result = db.execute('INSERT OR IGNORE INTO deals (hash, link, title, price, matched_item, ts) VALUES (?, ?, ?, ?, ?, ?)',
                            (digest, link, title, price, matched_item, time.time()))
    return digest if result.rowcount else None
