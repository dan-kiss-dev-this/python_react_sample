# FastAPI + React starter

## Context
Set up a minimal full-stack project in the empty `/Users/danielkiss/Code/python_react_sample`. The backend is FastAPI and the frontend is React. When the two dev servers run, the React page fetches data from the API.

Tools already installed: Python 3.11.2, Node 24.14, `uv`, and `npm`. Every step below can be copied and pasted by hand. Each command block starts from the project root.

## Layout
```
python_react_sample/
├── backend/          # uv project → backend/.venv
│   ├── pyproject.toml
│   ├── uv.lock
│   └── app/
│       ├── __init__.py
│       └── main.py
├── frontend/         # Vite React-TS app → frontend/node_modules
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts
│   └── src/App.tsx
├── .gitignore
└── README.md
```

## Dependency tracking
Each side has its own manifest and lockfile. Both lockfiles are committed. `.venv/` and `node_modules/` are gitignored.

| | Manifest | Lockfile | Add / remove | Fresh install |
|---|---|---|---|---|
| Backend | `backend/pyproject.toml` | `backend/uv.lock` | `uv add X`, `uv add --dev X`, `uv remove X` | `uv sync` |
| Frontend | `frontend/package.json` | `frontend/package-lock.json` | `npm install X`, `npm install -D X`, `npm uninstall X` | `npm ci` |

**Isolation:** `uv` creates the project-local venv `backend/.venv/` and installs everything there. Global Python is never touched. Always use `uv add` / `uv run` and never bare `pip`. Point the VS Code interpreter at `backend/.venv/bin/python`. Frontend packages live in `frontend/node_modules/`.

## Steps

### 1. Repo root
```bash
cd /Users/danielkiss/Code/python_react_sample
git init
```
Create `.gitignore`:
```
.venv/
__pycache__/
node_modules/
dist/
.env
.DS_Store
```

### 2. Backend
```bash
mkdir backend && cd backend
uv init --app --python 3.11 .
uv add "fastapi[standard]"
rm main.py                      # uv's placeholder; we use app/main.py
mkdir app && touch app/__init__.py
```
`uv init` also creates `backend/README.md` and `backend/.python-version`. Keep both.

Create `backend/app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/hello")
def hello(name: str = "world"):
    return {"message": f"Hello, {name}!"}
```
Run it from `backend/`:
```bash
uv run fastapi dev app/main.py   # http://localhost:8000, docs at /docs
```

### 3. Frontend (new terminal, from project root)
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```
If create-vite asks whether to install and start now, answer **No**, because the proxy needs configuring first.

Replace `frontend/vite.config.ts`:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Forward /api calls to FastAPI so the browser sees one origin (no CORS needed)
    proxy: { '/api': 'http://localhost:8000' },
  },
})
```
Replace `frontend/src/App.tsx`:
```tsx
import { useEffect, useState } from 'react'

function App() {
  const [message, setMessage] = useState('Loading...')

  useEffect(() => {
    fetch('/api/hello?name=React')
      .then((res) => res.json())
      .then((data) => setMessage(data.message))
      .catch(() => setMessage('Could not reach the backend'))
  }, [])

  return <h1>{message}</h1>
}

export default App
```
Run it from `frontend/`:
```bash
npm run dev   # http://localhost:5173
```

### 4. README
Write a root `README.md` with two sections:
- **Running it:** the backend and frontend run commands above, each in its own terminal.
- **Adding dependencies:** the commands from the dependency table.

## Verification
0. `cd backend && uv run python -c "import sys; print(sys.prefix)"` prints a path that ends in `backend/.venv`, which confirms the isolated env.
1. `curl localhost:8000/api/hello` returns `{"message":"Hello, world!"}`.
2. `localhost:8000/docs` loads the Swagger UI.
3. `localhost:5173` shows "Hello, React!", which was fetched through the proxy.
4. `cd frontend && npm run build` succeeds.

## Possible next steps (out of scope)
- Database with SQLModel and SQLite
- pytest for the backend and Vitest for the frontend
- Docker Compose, or FastAPI serving the built `frontend/dist` for production
