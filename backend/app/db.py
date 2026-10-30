import sqlite3

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    sector TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_bars (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    close  REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (ticker, date)
);
-- One row per weekday we've asked Massive about; holidays are stored with rows = 0
CREATE TABLE IF NOT EXISTS fetched_dates (
    date       TEXT PRIMARY KEY,
    rows       INTEGER NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS splits_applied (
    ticker         TEXT NOT NULL,
    execution_date TEXT NOT NULL,
    PRIMARY KEY (ticker, execution_date)
);
-- Tickers whose history we've already rebuilt across old symbols (renames)
CREATE TABLE IF NOT EXISTS history_checked (
    ticker     TEXT PRIMARY KEY,
    checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rs_ratings (
    date        TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    rs_score    REAL NOT NULL,
    rs_rating   INTEGER NOT NULL,
    ret_3m      REAL NOT NULL,
    ret_12m     REAL NOT NULL,
    rs_new_high INTEGER NOT NULL,
    PRIMARY KEY (date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_rs_ratings_ticker ON rs_ratings (ticker, date);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # WAL lets the API read while the ETL is writing
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn
