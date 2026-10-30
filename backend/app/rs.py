"""IBD-style Relative Strength (not RSI): 12-month price performance vs. a benchmark,
weighted toward the latest quarter, then ranked 1-99 across the universe."""

from bisect import bisect_left, bisect_right
from collections.abc import Sequence

LOOKBACKS = (63, 126, 189, 252)  # trading days: ~3, 6, 9, 12 months
WEIGHTS = (0.4, 0.2, 0.2, 0.2)
MIN_BARS = LOOKBACKS[-1] + 1
NEW_HIGH_WINDOW = 252

Closes = Sequence[float | None]


def weighted_performance(closes: Closes, i: int) -> float | None:
    """Weighted ratio of today's close to the close 63/126/189/252 days back."""
    if i < LOOKBACKS[-1]:
        return None
    today = closes[i]
    past = [closes[i - lb] for lb in LOOKBACKS]
    if today is None or any(p is None for p in past):
        return None
    return sum(w * today / p for w, p in zip(WEIGHTS, past))


def rs_score(stock_perf: float, benchmark_perf: float) -> float:
    """100 = matched the benchmark, 200 = twice the benchmark's weighted performance."""
    return 100 * stock_perf / benchmark_perf


def percentile_ratings(scores: dict[str, float]) -> dict[str, int]:
    """Rank scores 1-99; the best gets 99, the worst 1, and equal scores get equal ratings."""
    n = len(scores)
    if n == 0:
        return {}
    if n == 1:
        return {t: 99 for t in scores}
    ordered = sorted(scores.values())
    ratings = {}
    for ticker, score in scores.items():
        below = bisect_left(ordered, score)
        ties = bisect_right(ordered, score) - below
        pct = (below + (ties - 1) / 2) / (n - 1)
        ratings[ticker] = 1 + round(98 * pct)
    return ratings


def rs_line(closes: Closes, benchmark: Closes) -> list[float | None]:
    return [c / b if c is not None and b else None for c, b in zip(closes, benchmark)]


def is_new_high(line: Sequence[float | None], i: int, window: int = NEW_HIGH_WINDOW) -> bool:
    """True when line[i] is the highest value of the trailing window (IBD's 'blue dot')."""
    if i < window - 1 or line[i] is None:
        return False
    trailing = [v for v in line[i - window + 1 : i + 1] if v is not None]
    return line[i] >= max(trailing)


def compute_ratings(
    dates: Sequence[str], benchmark: Closes, closes_by_ticker: dict[str, Closes]
) -> list[dict]:
    """One row per (date, ticker) that has enough history. All series align with dates."""
    lines = {t: rs_line(c, benchmark) for t, c in closes_by_ticker.items()}
    rows = []
    for i in range(MIN_BARS - 1, len(dates)):
        bench_perf = weighted_performance(benchmark, i)
        if bench_perf is None:
            continue
        scores = {}
        for ticker, closes in closes_by_ticker.items():
            perf = weighted_performance(closes, i)
            if perf is not None:
                scores[ticker] = rs_score(perf, bench_perf)
        for ticker, rating in percentile_ratings(scores).items():
            closes = closes_by_ticker[ticker]
            rows.append(
                {
                    "date": dates[i],
                    "ticker": ticker,
                    "rs_score": scores[ticker],
                    "rs_rating": rating,
                    "ret_3m": closes[i] / closes[i - 63] - 1,
                    "ret_12m": closes[i] / closes[i - 252] - 1,
                    "rs_new_high": is_new_high(lines[ticker], i),
                }
            )
    return rows
