from contextlib import closing

from fastapi import FastAPI, HTTPException

from app.config import BENCHMARK
from app.db import connect

app = FastAPI()

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/hello")
def hello(name: str = "world"):
    return {"message": f"Hello, {name}"}

@app.get("/api/rs/status")
def rs_status():
    with closing(connect()) as conn:
        first, last, days = conn.execute(
            "SELECT MIN(date), MAX(date), COUNT(*) FROM daily_bars WHERE ticker = ?", (BENCHMARK,)
        ).fetchone()
        rated = conn.execute("SELECT MAX(date) FROM rs_ratings").fetchone()[0]
        tickers = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    return {
        "first_date": first,
        "latest_date": last,
        "rated_date": rated,
        "trading_days": days,
        "tickers": tickers,
        "benchmark": BENCHMARK,
    }

@app.get("/api/rs/sectors")
def rs_sectors():
    with closing(connect()) as conn:
        rows = conn.execute("SELECT DISTINCT sector FROM companies ORDER BY sector").fetchall()
    return [r["sector"] for r in rows]

@app.get("/api/rs/leaders")
def rs_leaders(limit: int = 50, sector: str | None = None):
    with closing(connect()) as conn:
        latest = conn.execute("SELECT MAX(date) FROM rs_ratings").fetchone()[0]
        if latest is None:
            return []
        # The rated day 5 trading days before the latest, for the 1-week change
        prev = conn.execute(
            "SELECT DISTINCT date FROM rs_ratings WHERE date < ? ORDER BY date DESC LIMIT 1 OFFSET 4",
            (latest,),
        ).fetchone()
        rows = conn.execute(
            """SELECT r.ticker, c.name, c.sector, b.close, r.rs_rating, r.rs_score,
                      r.ret_3m, r.ret_12m, r.rs_new_high,
                      r.rs_rating - p.rs_rating AS rating_change_1w
               FROM rs_ratings r
               JOIN companies c USING (ticker)
               JOIN daily_bars b ON b.ticker = r.ticker AND b.date = r.date
               LEFT JOIN rs_ratings p ON p.ticker = r.ticker AND p.date = :prev
               WHERE r.date = :latest AND (:sector IS NULL OR c.sector = :sector)
               ORDER BY r.rs_rating DESC, r.rs_score DESC
               LIMIT :limit""",
            {"latest": latest, "prev": prev[0] if prev else None, "sector": sector, "limit": limit},
        ).fetchall()
    return [{**dict(r), "rs_new_high": bool(r["rs_new_high"])} for r in rows]

@app.get("/api/rs/{ticker}")
def rs_ticker(ticker: str):
    ticker = ticker.upper()
    with closing(connect()) as conn:
        company = conn.execute("SELECT * FROM companies WHERE ticker = ?", (ticker,)).fetchone()
        if company is None:
            raise HTTPException(404, f"{ticker} is not in the S&P 500 list")
        series = conn.execute(
            """SELECT b.date, b.close, b.close / s.close AS rs_line, r.rs_rating
               FROM daily_bars b
               JOIN daily_bars s ON s.ticker = ? AND s.date = b.date
               LEFT JOIN rs_ratings r ON r.ticker = b.ticker AND r.date = b.date
               WHERE b.ticker = ?
               ORDER BY b.date""",
            (BENCHMARK, ticker),
        ).fetchall()
    return {**dict(company), "series": [dict(r) for r in series]}
