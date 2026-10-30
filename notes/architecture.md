# Architecture

## Backend

The ETL (`app/etl.py`) fills SQLite from two external sources. FastAPI (`app/main.py`) only reads from SQLite and never calls Massive.

```mermaid
flowchart LR
    subgraph ext["External sources"]
        CSV["GitHub constituents.csv<br/>S&P 500 tickers, names, sectors"]
        MAPI["Massive API<br/>api.massive.com<br/>free tier: 5 calls/min"]
    end

    subgraph etl["etl.py: uv run python -m app.etl"]
        direction TB
        E1["1. load_companies"]
        E2["2. fetch_prices<br/>one grouped-daily call per missing weekday"]
        E3["3. fix_renames<br/>short history or >3x jump → refetch_history"]
        E4["4. apply_splits<br/>stale bars → refetch_history"]
        E5["5. compute_rs"]
        E6["6. print_summary"]
        E1 --> E2 --> E3 --> E4 --> E5 --> E6
    end

    subgraph lib["Shared modules"]
        CFG["config.py<br/>loads .env, DB_PATH / MARKET_DB,<br/>MASSIVE_BASE_URL, BENCHMARK = SPY"]
        MC["massive.py: MassiveClient<br/>grouped_daily, ticker_daily,<br/>ticker_events, splits<br/>12.5 s spacing, 429 backoff"]
        RS["rs.py: pure functions<br/>weighted_performance, rs_score,<br/>percentile_ratings, rs_line, is_new_high"]
        DB["db.py: connect<br/>WAL mode + CREATE TABLE IF NOT EXISTS"]
    end

    subgraph sqlite["SQLite: backend/data/market.db"]
        T1[("companies")]
        T2[("daily_bars")]
        T3[("fetched_dates")]
        T4[("history_checked")]
        T5[("splits_applied")]
        T6[("rs_ratings")]
    end

    subgraph api["main.py: FastAPI on :8000"]
        A1["GET /api/rs/status"]
        A2["GET /api/rs/sectors"]
        A3["GET /api/rs/leaders?limit&sector"]
        A4["GET /api/rs/{ticker}"]
    end

    TEST["tests/test_rs.py<br/>uv run pytest"]

    CSV --> E1
    E2 & E3 & E4 --> MC
    MC <-->|"Bearer key from .env"| MAPI
    MC -.-> CFG
    DB -.-> CFG

    E1 -->|"replace"| T1
    E2 -->|"upsert, commit per day"| T2
    E2 --> T3
    E3 --> T2
    E3 --> T4
    E4 --> T2
    E4 --> T5
    E5 -->|"read closes"| T2
    E5 -->|"uses"| RS
    E5 -->|"replace"| T6

    etl -.->|"connect()"| DB
    api -.->|"connect()"| DB
    api -->|"read only"| sqlite
    TEST --> RS
```

## Frontend

The browser only talks to Vite, and Vite proxies `/api` to FastAPI. Sector filtering happens on the server; the chart range is sliced in the browser.

```mermaid
flowchart TB
    subgraph browser["Browser: localhost:5173"]
        MAIN["main.tsx<br/>mounts App, imports index.css"]
        CSS["index.css<br/>light + dark color tokens"]

        subgraph app["App.tsx: state and data loading"]
            S1["status, sectors<br/>loaded once on mount"]
            S2["sector → leaders<br/>refetched on sector change"]
            S3["selected → detail<br/>refetched on row click"]
            S4["range: 3M / 6M / 1Y / 2Y<br/>client-side only"]
        end

        FILTERS["Filter row<br/>sector select, range toggle,<br/>new-high legend"]
        LT["components/LeadersTable.tsx<br/>top 50: rating meter, 1W change,<br/>3M / 12M returns, blue dot"]

        subgraph rc["components/RsChart.tsx"]
            P1["Panel: Price"]
            P2["Panel: RS line indexed to 100"]
            P3["Panel: RS Rating with 80 line"]
        end

        APIC["api.ts<br/>types + getJson helpers"]
        RANGES["ranges.ts<br/>RANGES, Range type"]
        RECH["recharts<br/>LineChart, syncId = rs<br/>shared crosshair"]
    end

    VITE["Vite dev server<br/>proxy /api → :8000"]
    BE["FastAPI backend :8000"]

    MAIN --> app
    MAIN -.-> CSS
    app --> FILTERS
    app --> LT
    app --> rc
    FILTERS -->|"onChange"| S2
    FILTERS -->|"onClick"| S4
    LT -->|"onSelect ticker"| S3
    S4 --> rc
    rc --> RECH
    rc -.-> RANGES
    app -.-> RANGES

    S1 -->|"api.status(), api.sectors()"| APIC
    S2 -->|"api.leaders(sector)"| APIC
    S3 -->|"api.ticker(t)"| APIC
    APIC -->|"fetch /api/rs/*"| VITE
    VITE --> BE
```
