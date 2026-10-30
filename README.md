# FastAPI + React starter

## Running it

Start the backend and the frontend in separate terminals. Each command block starts from the project root.

**Terminal 1: backend**
```bash
cd backend
uv run fastapi dev app/main.py   # http://localhost:8000, docs at /docs
```

**Terminal 2: frontend**
```bash
cd frontend
npm run dev   # http://localhost:5173
```

Open http://localhost:5173. Vite forwards `/api` requests to the backend on port 8000.

## Data pipeline (S&P 500 RS Ratings)

The ETL pulls daily S&P 500 prices from [Massive](https://massive.com) (formerly Polygon.io) and computes IBD-style RS Ratings into `backend/data/market.db`. See `notes/setup2_pipeline.md` for the method.

1. Get a free Massive API key and add it to `backend/.env` (template: `backend/.env.example`):
   ```
   MASSIVE_API_KEY=your-key
   ```
2. Run the pipeline from `backend/`:
   ```bash
   uv run python -m app.etl            # first run: ~2 years of history, about 1 h 50 min
   uv run python -m app.etl            # later runs: only the missing days, a few seconds each
   uv run python -m app.etl --rs-only  # recompute ratings without calling the API
   ```
   The free tier allows 5 calls a minute, and each trading day takes one call. Every day is saved as soon as it arrives, so you can stop the run at any point and rerunning resumes it. Rerun it after the market closes to add the new day.
3. Run the tests from `backend/` with `uv run pytest`.

## Adding dependencies

Run the backend commands from `backend/` and the frontend commands from `frontend/`.

| | Add | Add (dev) | Remove | Fresh install |
|---|---|---|---|---|
| Backend | `uv add X` | `uv add --dev X` | `uv remove X` | `uv sync` |
| Frontend | `npm install X` | `npm install -D X` | `npm uninstall X` | `npm ci` |

Commit the lockfiles (`backend/uv.lock` and `frontend/package-lock.json`) along with the manifests. On the backend, use `uv` and never bare `pip`. Packages go into `backend/.venv/`, so your global Python stays untouched.
