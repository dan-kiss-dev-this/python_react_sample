import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TooltipContentProps } from 'recharts'
import type { Point, TickerDetail } from '../api'
import { RANGES } from '../ranges'
import type { Range } from '../ranges'

type Row = Point & { rs_index: number }

const fmtDate = (d: string) =>
  new Date(`${d}T00:00:00`).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
const fmtDay = (d: string) =>
  new Date(`${d}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

const AXIS_TICK = { fill: 'var(--text-muted)', fontSize: 12 }
const MARGIN = { top: 8, right: 56, bottom: 0, left: 0 }

function makeTooltip(label: string, format: (v: number) => string) {
  return function ChartTooltip({ active, payload }: TooltipContentProps) {
    const point = payload?.[0]
    if (!active || !point || point.value == null) return null
    return (
      <div className="tooltip">
        <div className="tooltip-date">{fmtDay((point.payload as Row).date)}</div>
        <div className="tooltip-row">
          <span className="line-key" aria-hidden="true" />
          <strong>{format(Number(point.value))}</strong>
          <span className="muted">{label}</span>
        </div>
      </div>
    )
  }
}

// Direct label on the last point only
function endLabel(rows: Row[], key: keyof Row, format: (v: number) => string) {
  return function EndLabel(props: { x?: number | string; y?: number | string; index?: number }) {
    const value = rows[props.index ?? -1]?.[key]
    if (props.index !== rows.length - 1 || typeof value !== 'number') return null
    return (
      <text x={Number(props.x) + 8} y={Number(props.y)} dy={4} className="end-label">
        {format(value)}
      </text>
    )
  }
}

type PanelProps = {
  title: string
  subtitle: string
  rows: Row[]
  dataKey: keyof Row
  format: (v: number) => string
  height: number
  showXAxis?: boolean
  domain?: [number, number]
  reference?: { y: number; label: string }
}

function Panel({ title, subtitle, rows, dataKey, format, height, showXAxis, domain, reference }: PanelProps) {
  return (
    <figure className="panel">
      <figcaption>
        <span className="panel-title">{title}</span>
        <span className="muted">{subtitle}</span>
      </figcaption>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={rows} syncId="rs" margin={MARGIN}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis
            dataKey="date"
            hide={!showXAxis}
            tickFormatter={fmtDate}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={{ stroke: 'var(--axis)' }}
            minTickGap={48}
          />
          <YAxis
            domain={domain ?? ['auto', 'auto']}
            tickFormatter={(v: number) => format(v)}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={false}
            width={52}
            tickCount={4}
          />
          {reference && (
            <ReferenceLine
              y={reference.y}
              stroke="var(--axis)"
              label={{ value: reference.label, position: 'insideTopLeft', fill: 'var(--text-muted)', fontSize: 12 }}
            />
          )}
          <Tooltip
            content={makeTooltip(title, format)}
            cursor={{ stroke: 'var(--axis)', strokeWidth: 1 }}
            isAnimationActive={false}
          />
          <Line
            dataKey={dataKey}
            stroke="var(--series-1)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            dot={false}
            activeDot={{ r: 4, fill: 'var(--series-1)', stroke: 'var(--surface)', strokeWidth: 2 }}
            label={endLabel(rows, dataKey, format)}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </figure>
  )
}

type Props = { detail: TickerDetail; range: Range; benchmark: string; loading: boolean }

export default function RsChart({ detail, range, benchmark, loading }: Props) {
  const series = detail.series.slice(-Math.min(RANGES[range], detail.series.length))
  const base = series[0]?.rs_line ?? 1
  const rows: Row[] = series.map((p) => ({ ...p, rs_index: (100 * p.rs_line) / base }))
  const firstRated = rows.find((r) => r.rs_rating !== null)

  return (
    <section className={`chart-card${loading ? ' is-loading' : ''}`} aria-label={`${detail.ticker} charts`}>
      <header className="chart-header">
        <h2>
          {detail.ticker} <span className="muted">{detail.name}</span>
        </h2>
        <p className="muted">{detail.sector}</p>
      </header>
      <Panel
        title="Price"
        subtitle="Daily close, split-adjusted"
        rows={rows}
        dataKey="close"
        format={(v) => `$${v.toFixed(v >= 1000 ? 0 : 2)}`}
        height={180}
      />
      <Panel
        title="RS line"
        subtitle={`Price ÷ ${benchmark}, indexed to 100 at the start of the range. Rising = beating the S&P 500`}
        rows={rows}
        dataKey="rs_index"
        format={(v) => v.toFixed(0)}
        height={150}
        reference={{ y: 100, label: `Even with ${benchmark}` }}
      />
      <Panel
        title="RS Rating"
        subtitle={
          firstRated
            ? 'Percentile rank 1–99 within the S&P 500'
            : 'No ratings in this range yet (each rating needs 12 months of history)'
        }
        rows={rows}
        dataKey="rs_rating"
        format={(v) => v.toFixed(0)}
        height={150}
        domain={[0, 100]}
        reference={{ y: 80, label: '80: IBD buy threshold' }}
        showXAxis
      />
    </section>
  )
}
