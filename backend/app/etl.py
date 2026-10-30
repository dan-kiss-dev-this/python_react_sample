"""Extract S&P 500 prices from Massive, transform them into RS Ratings, load into SQLite.

Run from backend/:  uv run python -m app.etl [--days N] [--rs-only]
Resumable: each trading day is committed as soon as it's fetched.
"""

import argparse
import csv
import io
import sqlite3
from datetime import date, timedelta

import httpx

from app import rs
from app.config import BENCHMARK, CONSTITUENTS_URL
from app.db import connect
from app.massive import MIN_SECONDS_BETWEEN_CALLS, MassiveClient, bar_date

DEFAULT_DAYS = 725  # just inside the free tier's 2-year history limit
# An empty result this recent may just mean Massive hasn't published the day yet
RECENT_DAYS_GRACE = 3


def load_companies(conn: sqlite3.Connection) -> set[str]:
    resp = httpx.get(CONSTITUENTS_URL, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    rows = [
        (r["Symbol"].strip(), r["Security"].strip(), r["GICS Sector"].strip())
        for r in csv.DictReader(io.StringIO(resp.text))
    ]
    with conn:
        conn.execute("DELETE FROM companies")
        conn.executemany("INSERT INTO companies VALUES (?, ?, ?)", rows)
    print(f"Constituents: {len(rows)} companies")
    return {r[0] for r in rows}


def weekdays(start: date, end: date) -> list[str]:
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def fetch_prices(conn: sqlite3.Connection, client: MassiveClient, tickers: set[str], days: int) -> None:
    today = date.today()
    done = {r["date"] for r in conn.execute("SELECT date FROM fetched_dates")}
    todo = [d for d in weekdays(today - timedelta(days=days), today - timedelta(days=1)) if d not in done]
    if not todo:
        print("Prices: up to date")
        return
    minutes = len(todo) * MIN_SECONDS_BETWEEN_CALLS / 60
    print(f"Prices: {len(todo)} days to fetch (~{minutes:.0f} min at the free-tier rate limit)")

    wanted = tickers | {BENCHMARK}
    for n, day in enumerate(todo, 1):
        try:
            results = client.grouped_daily(day)
        except httpx.HTTPStatusError as e:
            # e.g. 403 for a date outside the plan's history window; leave it unmarked
            print(f"  [{n}/{len(todo)}] {day}: HTTP {e.response.status_code}, skipped")
            continue
        rows = [(r["T"], day, r["c"], r.get("v", 0)) for r in results if r["T"] in wanted]
        if not rows and (today - date.fromisoformat(day)).days <= RECENT_DAYS_GRACE:
            print(f"  [{n}/{len(todo)}] {day}: no data yet, will retry next run")
            continue
        with conn:
            conn.executemany("INSERT OR REPLACE INTO daily_bars VALUES (?, ?, ?, ?)", rows)
            conn.execute(
                "INSERT OR REPLACE INTO fetched_dates VALUES (?, ?, ?)",
                (day, len(rows), today.isoformat()),
            )
        label = f"{len(rows)} bars" if rows else "market closed"
        print(f"  [{n}/{len(todo)}] {day}: {label}")


def apply_splits(conn: sqlite3.Connection, client: MassiveClient, tickers: set[str]) -> None:
    """Refetch a ticker's history when a split happened after some of its bars were fetched.

    Bars are split-adjusted as of the day they were fetched, so only bars fetched on or
    before the execution date are stale.
    """
    first = conn.execute("SELECT MIN(date) FROM fetched_dates WHERE rows > 0").fetchone()[0]
    if not first:
        return
    applied = {(r["ticker"], r["execution_date"]) for r in conn.execute("SELECT * FROM splits_applied")}
    splits = [
        s for s in client.splits(since=first)
        if s["ticker"] in tickers and (s["ticker"], s["execution_date"]) not in applied
    ]
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    refetched = 0
    for s in splits:
        ticker, executed = s["ticker"], s["execution_date"]
        stale = conn.execute(
            """SELECT 1 FROM daily_bars b JOIN fetched_dates f ON f.date = b.date
               WHERE b.ticker = ? AND b.date < ? AND f.fetched_at <= ? LIMIT 1""",
            (ticker, executed, executed),
        ).fetchone()
        if stale:
            bars = client.ticker_daily(ticker, first, yesterday)
            print(f"  split {ticker} {s['split_from']:g}:{s['split_to']:g} on {executed}: refetched {len(bars)} bars")
            with conn:
                conn.execute("DELETE FROM daily_bars WHERE ticker = ?", (ticker,))
                conn.executemany(
                    "INSERT INTO daily_bars VALUES (?, ?, ?, ?)",
                    [(ticker, bar_date(b), b["c"], b.get("v", 0)) for b in bars],
                )
            refetched += 1
        with conn:
            conn.execute("INSERT INTO splits_applied VALUES (?, ?)", (ticker, executed))
    print(f"Splits: {len(splits)} new for S&P tickers, {refetched} refetched")


def compute_rs(conn: sqlite3.Connection) -> None:
    bench_rows = conn.execute(
        "SELECT date, close FROM daily_bars WHERE ticker = ? ORDER BY date", (BENCHMARK,)
    ).fetchall()
    dates = [r["date"] for r in bench_rows]
    benchmark = [r["close"] for r in bench_rows]
    index = {d: i for i, d in enumerate(dates)}

    closes_by_ticker: dict[str, list[float | None]] = {
        r["ticker"]: [None] * len(dates) for r in conn.execute("SELECT ticker FROM companies")
    }
    for r in conn.execute(
        "SELECT b.ticker, b.date, b.close FROM daily_bars b JOIN companies c USING (ticker)"
    ):
        i = index.get(r["date"])
        if i is not None:
            closes_by_ticker[r["ticker"]][i] = r["close"]

    rows = rs.compute_ratings(dates, benchmark, closes_by_ticker)
    with conn:
        conn.execute("DELETE FROM rs_ratings")
        conn.executemany(
            """INSERT INTO rs_ratings VALUES
               (:date, :ticker, :rs_score, :rs_rating, :ret_3m, :ret_12m, :rs_new_high)""",
            rows,
        )
    rated_days = len({r["date"] for r in rows})
    print(f"RS: {len(rows)} ratings across {rated_days} days")
    if not rows:
        print(f"  (needs {rs.MIN_BARS} trading days of {BENCHMARK}; have {len(dates)})")


def print_summary(conn: sqlite3.Connection) -> None:
    first, last, days = conn.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) FROM daily_bars WHERE ticker = ?", (BENCHMARK,)
    ).fetchone()
    tickers = conn.execute("SELECT COUNT(DISTINCT ticker) FROM daily_bars").fetchone()[0]
    rated = conn.execute("SELECT MAX(date) FROM rs_ratings").fetchone()[0]
    print(f"\nSummary: {first} → {last}, {days} trading days, {tickers} tickers, latest rating {rated}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="calendar days of history to keep")
    parser.add_argument("--rs-only", action="store_true", help="skip fetching; just recompute RS")
    args = parser.parse_args()

    conn = connect()
    if not args.rs_only:
        client = MassiveClient()
        tickers = load_companies(conn)
        fetch_prices(conn, client, tickers, args.days)
        apply_splits(conn, client, tickers)
    compute_rs(conn)
    print_summary(conn)


if __name__ == "__main__":
    main()
