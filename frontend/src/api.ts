export type Status = {
  first_date: string | null
  latest_date: string | null
  rated_date: string | null
  trading_days: number
  tickers: number
  benchmark: string
}

export type Leader = {
  ticker: string
  name: string
  sector: string
  close: number
  rs_rating: number
  rs_score: number
  ret_3m: number
  ret_12m: number
  rs_new_high: boolean
  rating_change_1w: number | null
}

export type Point = {
  date: string
  close: number
  rs_line: number
  rs_rating: number | null
}

export type TickerDetail = {
  ticker: string
  name: string
  sector: string
  series: Point[]
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} (${url})`)
  return res.json()
}

export const api = {
  status: () => getJson<Status>('/api/rs/status'),
  sectors: () => getJson<string[]>('/api/rs/sectors'),
  leaders: (sector: string | null, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (sector) params.set('sector', sector)
    return getJson<Leader[]>(`/api/rs/leaders?${params}`)
  },
  ticker: (ticker: string) => getJson<TickerDetail>(`/api/rs/${encodeURIComponent(ticker)}`),
}

// IBD needs 252 prior trading days before the first rating
export const MIN_BARS = 253
