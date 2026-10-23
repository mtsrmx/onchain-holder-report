"""Local cache of everything read from the chain and the explorer.

The cache lives in cache/chain.sqlite. It holds per-address data, so it is
not published with the report; only the aggregates in data/ are. Anyone can
rebuild it with the scripts in scripts/.
"""
import sqlite3

from .config import CACHE

SCHEMA = """
CREATE TABLE IF NOT EXISTS progress (name TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS seen (address TEXT PRIMARY KEY, first_block INTEGER, how TEXT);
CREATE TABLE IF NOT EXISTS block_fees (number INTEGER PRIMARY KEY, n_tx INTEGER, fee_wei TEXT);
CREATE TABLE IF NOT EXISTS logs (block INTEGER, tx_hash TEXT, log_index INTEGER, address TEXT,
    t0 TEXT, t1 TEXT, t2 TEXT, t3 TEXT, data TEXT, PRIMARY KEY (tx_hash, log_index));
CREATE TABLE IF NOT EXISTS receipts_q (block INTEGER, tx_hash TEXT PRIMARY KEY, tx_index INTEGER,
    sender TEXT, recipient TEXT, created TEXT, status INTEGER, gas_used INTEGER, gas_price TEXT);
CREATE TABLE IF NOT EXISTS txs_q (tx_hash TEXT PRIMARY KEY, block INTEGER, sender TEXT, recipient TEXT,
    value TEXT, input4 TEXT);
CREATE TABLE IF NOT EXISTS internal (block INTEGER, tx_hash TEXT, trace_id TEXT, sender TEXT, recipient TEXT,
    value TEXT, kind TEXT, created TEXT, is_error INTEGER, PRIMARY KEY (tx_hash, trace_id));
CREATE TABLE IF NOT EXISTS explorer_list (address TEXT PRIMARY KEY, listed_balance TEXT, name TEXT, page INTEGER);
CREATE TABLE IF NOT EXISTS snapshots (label TEXT PRIMARY KEY, kind TEXT, target_ts INTEGER, block INTEGER, block_ts INTEGER);
CREATE TABLE IF NOT EXISTS native (address TEXT, block INTEGER, wei TEXT, PRIMARY KEY (address, block));
CREATE TABLE IF NOT EXISTS wrbnt (address TEXT, block INTEGER, wei TEXT, PRIMARY KEY (address, block));
CREATE TABLE IF NOT EXISTS staked (pool TEXT, address TEXT, block INTEGER, wei TEXT, PRIMARY KEY (pool, address, block));
CREATE TABLE IF NOT EXISTS code (address TEXT PRIMARY KEY, block INTEGER, is_contract INTEGER, code_len INTEGER);
CREATE TABLE IF NOT EXISTS contract_meta (address TEXT PRIMARY KEY, name TEXT, verified INTEGER, source_sha256 TEXT);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""


def connect():
    CACHE.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(CACHE / "chain.sqlite", timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.executescript(SCHEMA)
    return db


def get_progress(db, name, default=None):
    r = db.execute("SELECT value FROM progress WHERE name=?", (name,)).fetchone()
    return r[0] if r else default


def set_progress(db, name, value):
    db.execute("INSERT OR REPLACE INTO progress VALUES (?,?)", (name, str(value)))


def kv_get(db, k, default=None):
    r = db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return r[0] if r else default


def kv_set(db, k, v):
    db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (k, str(v)))


def snapshot_blocks(db, kind=None):
    q = "SELECT label, kind, target_ts, block, block_ts FROM snapshots"
    rows = db.execute(q + (" WHERE kind=?" if kind else "") + " ORDER BY target_ts", (kind,) if kind else ()).fetchall()
    return rows
