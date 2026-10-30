import type { Leader } from '../api'

type Props = {
  leaders: Leader[]
  selected: string | null
  onSelect: (ticker: string) => void
  loading: boolean
}

const pct = (v: number) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`

function Change({ value }: { value: number | null }) {
  if (value === null) return <span className="muted">–</span>
  if (value === 0) return <span className="muted">0</span>
  const up = value > 0
  return (
    <span className={up ? 'delta-up' : 'delta-down'}>
      <span aria-hidden="true">{up ? '▲' : '▼'}</span> {Math.abs(value)}
      <span className="sr-only">{up ? ' up' : ' down'}</span>
    </span>
  )
}

export default function LeadersTable({ leaders, selected, onSelect, loading }: Props) {
  return (
    <div className={`table-wrap${loading ? ' is-loading' : ''}`}>
      <table className="leaders">
        <thead>
          <tr>
            <th className="num">#</th>
            <th>Stock</th>
            <th className="num">RS Rating</th>
            <th className="num" title="Rating change vs. 5 trading days ago">1W</th>
            <th className="num">3M</th>
            <th className="num">12M</th>
            <th className="num">Close</th>
          </tr>
        </thead>
        <tbody>
          {leaders.map((l, i) => (
            <tr
              key={l.ticker}
              className={l.ticker === selected ? 'selected' : undefined}
              aria-selected={l.ticker === selected}
              tabIndex={0}
              onClick={() => onSelect(l.ticker)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelect(l.ticker)
                }
              }}
            >
              <td className="num muted">{i + 1}</td>
              <td>
                <div className="stock">
                  <span className="ticker">{l.ticker}</span>
                  {l.rs_new_high && (
                    <span className="new-high" title="RS line at a 52-week high">
                      <span className="sr-only">RS line at a 52-week high</span>
                    </span>
                  )}
                </div>
                <div className="name">{l.name}</div>
              </td>
              <td className="num">
                <div className="rating">
                  <span className="rating-value">{l.rs_rating}</span>
                  <span className="meter" aria-hidden="true">
                    <span style={{ width: `${l.rs_rating}%` }} />
                  </span>
                </div>
              </td>
              <td className="num"><Change value={l.rating_change_1w} /></td>
              <td className="num">{pct(l.ret_3m)}</td>
              <td className="num">{pct(l.ret_12m)}</td>
              <td className="num">{l.close.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
