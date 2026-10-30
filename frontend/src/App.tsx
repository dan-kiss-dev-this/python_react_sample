import { useEffect, useState } from 'react'
import { api, MIN_BARS } from './api'
import type { Leader, Status, TickerDetail } from './api'
import LeadersTable from './components/LeadersTable'
import RsChart from './components/RsChart'
import { RANGES } from './ranges'
import type { Range } from './ranges'

function App() {
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sectors, setSectors] = useState<string[]>([])
  const [sector, setSector] = useState<string | null>(null)
  // Results are tagged with the sector they were fetched for, so loading is derived
  const [leaders, setLeaders] = useState<{ sector: string | null; rows: Leader[] } | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<TickerDetail | null>(null)
  const [range, setRange] = useState<Range>('1Y')

  useEffect(() => {
    Promise.all([api.status(), api.sectors()])
      .then(([s, sec]) => {
        setStatus(s)
        setSectors(sec)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!status?.rated_date) return
    let cancelled = false
    api
      .leaders(sector)
      .then((rows) => {
        if (cancelled) return
        setLeaders({ sector, rows })
        // Keep the selection if it survived the filter; otherwise pick the leader
        setSelected((cur) => (cur && rows.some((r) => r.ticker === cur) ? cur : (rows[0]?.ticker ?? null)))
      })
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [status, sector])

  useEffect(() => {
    if (!selected) return
    let cancelled = false
    api
      .ticker(selected)
      .then((d) => !cancelled && setDetail(d))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [selected])

  if (error) {
    return (
      <main className="app">
        <div className="notice">
          <h2>Could not load data</h2>
          <p>{error}</p>
          <p className="muted">Is the backend running? <code>cd backend && uv run fastapi dev app/main.py</code></p>
        </div>
      </main>
    )
  }

  if (!status) return <main className="app"><p className="muted">Loading…</p></main>

  return (
    <main className="app">
      <header className="app-header">
        <h1>S&amp;P 500 RS Leaders</h1>
        <p className="muted">
          IBD-style Relative Strength: 12-month performance vs. {status.benchmark}, weighted toward the latest
          quarter, ranked 1–99. Not RSI.
          {status.rated_date && <> Ratings as of <strong>{status.rated_date}</strong>.</>}
        </p>
      </header>

      {!status.rated_date ? (
        <div className="notice">
          <h2>No RS ratings yet</h2>
          <p>
            {status.trading_days} of {MIN_BARS} trading days loaded. Each rating needs 12 months of prices.
          </p>
          <p className="muted">
            Run the pipeline from <code>backend/</code>: <code>uv run python -m app.etl</code>, then reload.
          </p>
        </div>
      ) : (
        <>
          <div className="filters" role="toolbar" aria-label="Filters">
            <label>
              <span className="muted">Sector</span>
              <select value={sector ?? ''} onChange={(e) => setSector(e.target.value || null)}>
                <option value="">All sectors</option>
                {sectors.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>
            <div className="segmented" role="group" aria-label="Chart range">
              {(Object.keys(RANGES) as Range[]).map((r) => (
                <button key={r} type="button" aria-pressed={r === range} onClick={() => setRange(r)}>
                  {r}
                </button>
              ))}
            </div>
            <span className="legend-note muted">
              <span className="new-high" aria-hidden="true" /> RS line at a 52-week high
            </span>
          </div>

          <div className="layout">
            <LeadersTable
              leaders={leaders?.rows ?? []}
              selected={selected}
              onSelect={setSelected}
              loading={leaders?.sector !== sector}
            />
            {detail ? (
              <RsChart
                detail={detail}
                range={range}
                benchmark={status.benchmark}
                loading={detail.ticker !== selected}
              />
            ) : (
              <div className="chart-card muted">Select a stock</div>
            )}
          </div>
        </>
      )}
    </main>
  )
}

export default App
