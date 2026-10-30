# S&P 500 Relative Strength (RS) Rating ETL + chart

## Context
The repo is a bare FastAPI + React starter. `backend/app/main.py` has only `/api/health` and `/api/hello`, `frontend/src/App.tsx` fetches `/api/hello`, and Vite proxies `/api` to port 8000. The goal is a small ETL pipeline that pulls S&P 500 daily prices from **Massive** (formerly Polygon.io, free key) and computes an **IBD-style RS Rating**: price performance against a benchmark, ranked 1–99. This is **not RSI**. The results are shown as an "IBD 50"-style leaders list plus a chart.

The free Massive tier allows 5 calls a minute, provides end-of-day data only, and covers 2 years of history. The **Daily Market Summary** (grouped daily) endpoint returns every US stock for one date in one call, so one call covers one trading day for all ~500 tickers.

## Decisions (from the review)
| # | Decision | Choice |
|---|---|---|
| 1 | Purpose | Learning project, but accurate enough to trust for real screening later |
| 2 | History | Full free-tier 2 years: about 520 calls, ~1 h 50 min one-time backfill, about 1 year of RS Rating history from day one |
| 3 | Benchmark | SPY (matches IBD) |
| 4 | Daily update | Manual `uv run python -m app.etl`, which catches up any missed days. A "Refresh" button is a later follow-up |
| 5 | Tests | pytest for `rs.py` only |
| 6 | Universe | Rank within the S&P 500 only (default, kept from the original plan) |
| 7 | Splits | Handled automatically via the free splits endpoint (default, added because of decision 1) |

## RS method (IBD approximation)
- Benchmark: **SPY**, used as the S&P 500 proxy.
- Weighted 12-month performance, with the most recent quarter counting double:
  `perf = 0.4·C/C₆₃ + 0.2·C/C₁₂₆ + 0.2·C/C₁₈₉ + 0.2·C/C₂₅₂` (subscripts are trading days back).
- `rs_score = 100 · perf_stock / perf_SPY`. A score above 100 means the stock is beating the S&P.
- `rs_rating` = the percentile rank (1–99) of `rs_score` across the S&P 500 on that date. Caveat: IBD ranks against roughly 6,000 stocks, so our 99 means "top 1% of the S&P 500".
- **RS line** = `close / SPY close`, the classic line on IBD charts. We also flag when the RS line makes a new 52-week high (IBD's "blue dot").
- A rating needs at least 253 bars, so only dates with 252 prior trading days get one.

## Layout (new/changed files)
```
backend/
  .env.example          # MASSIVE_API_KEY=   (real .env is already gitignored)
  data/market.db        # SQLite, created by ETL; add backend/data/ to .gitignore
  app/
    config.py           # loads .env (python-dotenv), DB path, API base URL
    db.py               # sqlite3 connect + CREATE TABLE IF NOT EXISTS
    massive.py          # tiny httpx client: grouped_daily(date), rate-limited
    etl.py              # extract → transform → load; `uv run python -m app.etl`
    rs.py               # pure functions: weighted perf, score, percentile, RS line
    main.py             # + /api/rs/* endpoints
frontend/src/
  api.ts                # TS types + fetch helpers
  components/LeadersTable.tsx
  components/RsChart.tsx
  App.tsx               # replaces hello demo
notes/setup2_pipeline.md  # copy of this plan, matching notes/setup1.md convention
```

## Backend

**Dependencies** (run from `backend/`): `uv add python-dotenv`. `httpx` already ships with `fastapi[standard]`, and storage uses stdlib `sqlite3`. No pandas, because the math is simple loops over ~500 tickers.

**Config / secrets:** `backend/.env` holds `MASSIVE_API_KEY=...`. Base URL is `https://api.massive.com` (kept as a constant; `api.polygon.io` is the legacy host). The key is sent as an `Authorization: Bearer` header so it never shows up in URLs or logs.

**Schema (`db.py`):**
- `companies(ticker PK, name, sector)`
- `daily_bars(ticker, date, close, volume, PK(ticker, date))`, which includes `SPY`
- `fetched_dates(date PK, rows, fetched_at)`, which marks holidays (0 rows) as done so they're never re-fetched
- `splits_applied(ticker, execution_date, PK(ticker, execution_date))`
- `rs_ratings(date, ticker, rs_score, rs_rating, ret_3m, ret_12m, rs_line, rs_new_high, PK(date, ticker))`

**ETL (`etl.py`), resumable and incremental:**
1. **Extract constituents:** GET the CSV at `https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv` (Symbol, Security, GICS Sector) and upsert it into `companies`.
2. **Extract prices:** for every weekday from `today − --days` (default **725** calendar days, just inside the free tier's 2-year limit; about 520 calls and ~1 h 50 min the first time) through yesterday that isn't in `fetched_dates`, call `GET /v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=true`. Sleep ~12.5 s between calls to stay under 5 a minute. On a 429, back off 60 s and retry.
3. **Transform + load prices:** keep only results whose `T` is in the S&P set ∪ {SPY}. Upsert `(T, date, c, v)` into `daily_bars` and insert into `fetched_dates`. **Commit per date**, so Ctrl-C loses nothing and a rerun resumes where it stopped.
4. **Splits:** call `GET /stocks/v1/splits?execution_date.gte=<oldest stored date>` once per run. Stored bars are adjusted as of the day they were *fetched*, so a split only invalidates bars that were fetched before it executed. For each S&P ticker's split not yet in `splits_applied`, check whether any of its bars dated before `execution_date` came from a date whose `fetched_at` is earlier than `execution_date`. If so, delete its bars and refetch the full history with one `GET /v2/aggs/ticker/{T}/range/1/day/{from}/{to}?adjusted=true` call. Either way, record the split. The first backfill causes no refetches, and later runs usually need 0–2 extra calls.
5. **Transform RS:** recompute `rs_ratings` for every date that has 253+ bars of history (using `rs.py`) and replace the table contents. This is cheap: about 500 tickers × a few hundred dates.
6. Print a summary: date range, trading days, SPY bar count, latest rating date.

After the first backfill, a daily rerun costs one API call. Flags: `--days N`, `--rs-only` (skip fetching, recompute RS). Remaining limitation: survivorship bias. We use *today's* S&P 500 list for the whole history, so companies that were removed from the index don't appear in past ratings.

**API (`main.py`):**
- `GET /api/rs/status` → `{latest_date, first_date, trading_days, tickers}`
- `GET /api/rs/leaders?limit=50&sector=` → the latest date's top N by `rs_rating`: ticker, name, sector, close, rs_rating, rating change vs. 5 trading days ago, ret_3m, ret_12m, rs_new_high
- `GET /api/rs/sectors` → the list of sectors, for the filter dropdown
- `GET /api/rs/{ticker}` → time series `[{date, close, rs_line, rs_rating|null}]` plus company info; 404 if unknown

## Frontend
- `npm install recharts` (from `frontend/`).
- **Load the `dataviz` skill before writing chart code** (colors, axes, tooltips, light/dark).
- `App.tsx`: a header with the "as of" date from `/api/rs/status`, a sector filter, and **LeadersTable** (the top 50 by RS Rating, with a rating chip, 1-week change ▲▼, 3M/12M returns, and a blue dot when the RS line is at a new high). Clicking a row selects that ticker. The first row is selected by default.
- `RsChart.tsx` for the selected ticker has two stacked charts sharing the date axis:
  1. Price (left axis) and RS line (right axis, normalized to 100 at the start), with a range toggle of 3M/6M/1Y/2Y.
  2. RS Rating history (0–99 band, with a reference line at 80, IBD's usual buy threshold).
- An empty or error state that tells you to run the ETL when `/api/rs/status` has no data.

## Steps to execute
1. `.gitignore`: add `backend/data/`. Create `backend/.env.example`. You create `backend/.env` with your key yourself, and I won't read or print it.
2. Backend: `uv add python-dotenv` and `uv add --dev pytest`, then write `config.py`, `db.py`, `massive.py`, `rs.py` (plus `backend/tests/test_rs.py`), `etl.py`, and the endpoints in `main.py`.
3. Run a quick smoke test with `uv run python -m app.etl --days 10` (about 2 minutes) to confirm the API key, the parsing, and that SPY is present in the grouped results. If SPY is missing, fall back to a single `/v2/aggs/ticker/SPY/range/1/day/{from}/{to}` call.
4. Start the full backfill (`uv run python -m app.etl`, ~1 h 50 min) in the background while building the frontend.
5. Frontend: `npm install recharts`, then write `api.ts`, the components, and `App.tsx`.
6. Update `README.md` with a "Data pipeline" section (the .env setup, the ETL command, how long it takes, and how to rerun it daily).

## Verification
- `uv run pytest` (from `backend/`): `tests/test_rs.py` checks that a stock that doubled while SPY was flat gets `rs_score` ≈ 200, that percentiles span 1–99 with ties handled consistently, that tickers with fewer than 253 bars get no rating, and that the RS-line new-high flag works.
- After the ETL, `sqlite3 backend/data/market.db "select count(*) from daily_bars where ticker='SPY'"` should equal the trading-day count, and `select count(distinct ticker) from daily_bars` should be about 500.
- `curl localhost:8000/api/rs/leaders?limit=5` and `curl localhost:8000/api/rs/NVDA` should return sensible JSON. Spot-check one RS rating against intuition (for example, recent big winners near 99).
- Open `localhost:5173`, run the `run` skill or the Chrome tools to screenshot the table and chart, click a few rows, and switch the sector filter and the range toggle.
- `cd frontend && npm run build && npm run lint` should pass.

## Out of scope / next steps
- A "Refresh" button that triggers the ETL from the UI, and scheduling the daily ETL (cron/launchd)
- Ranking against a broader universe (Russell 1000) to get closer to true IBD ratings
- Sector/industry-group RS, and a composite rating with EPS (IBD's CAN SLIM)
