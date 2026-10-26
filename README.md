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

## Adding dependencies

Run the backend commands from `backend/` and the frontend commands from `frontend/`.

| | Add | Add (dev) | Remove | Fresh install |
|---|---|---|---|---|
| Backend | `uv add X` | `uv add --dev X` | `uv remove X` | `uv sync` |
| Frontend | `npm install X` | `npm install -D X` | `npm uninstall X` | `npm ci` |

Commit the lockfiles (`backend/uv.lock` and `frontend/package-lock.json`) along with the manifests. On the backend, use `uv` and never bare `pip`. Packages go into `backend/.venv/`, so your global Python stays untouched.
