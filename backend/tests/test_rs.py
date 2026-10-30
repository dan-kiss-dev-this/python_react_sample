import pytest

from app import rs

N = rs.MIN_BARS  # exactly enough bars for one rating, at index N - 1


def flat(value: float = 100.0, n: int = N) -> list[float]:
    return [value] * n


def test_weighted_performance_needs_252_prior_bars():
    closes = flat()
    assert rs.weighted_performance(closes, N - 2) is None
    assert rs.weighted_performance(closes, N - 1) == pytest.approx(1.0)


def step(at: int) -> list[float]:
    """100 before index `at`, 150 from `at` on: a one-off 50% gain."""
    return [100.0] * at + [150.0] * (N - at)


def test_weighted_performance_favors_recent_gains():
    # Every leg compares against today's close, so a gain shows up in each leg that
    # reaches back past it. Recent gains appear in more (and heavier) legs.
    assert rs.weighted_performance(step(10), N - 1) == pytest.approx(0.8 + 0.2 * 1.5)  # 9-12 months ago
    assert rs.weighted_performance(step(150), N - 1) == pytest.approx(0.4 + 0.6 * 1.5)  # 3-6 months ago
    assert rs.weighted_performance(step(200), N - 1) == pytest.approx(1.5)  # last quarter


def test_weighted_performance_missing_close_is_none():
    closes: list[float | None] = flat()
    closes[N - 1 - 126] = None
    assert rs.weighted_performance(closes, N - 1) is None


def test_doubled_stock_vs_flat_benchmark_scores_200():
    stock = flat(100.0, N - 1) + [200.0]
    perf = rs.weighted_performance(stock, N - 1)
    bench = rs.weighted_performance(flat(), N - 1)
    assert rs.rs_score(perf, bench) == pytest.approx(200.0)


def test_percentile_ratings_span_1_to_99():
    ratings = rs.percentile_ratings({f"T{i}": float(i) for i in range(500)})
    assert ratings["T0"] == 1
    assert ratings["T499"] == 99
    assert ratings["T250"] == 50
    values = [ratings[f"T{i}"] for i in range(500)]
    assert values == sorted(values)


def test_percentile_ratings_ties_get_equal_ratings():
    ratings = rs.percentile_ratings({"A": 1.0, "B": 5.0, "C": 5.0, "D": 9.0})
    assert ratings["B"] == ratings["C"]
    assert ratings["A"] < ratings["B"] < ratings["D"]


def test_percentile_ratings_edge_sizes():
    assert rs.percentile_ratings({}) == {}
    assert rs.percentile_ratings({"A": 1.0}) == {"A": 99}


def test_is_new_high():
    rising = [float(i) for i in range(300)]
    assert rs.is_new_high(rising, 299)
    assert not rs.is_new_high(rising, 100)  # not enough trailing history
    dipped = rising[:-1] + [10.0]
    assert not rs.is_new_high(dipped, 299)


def test_compute_ratings_ranks_and_skips_short_history():
    dates = [f"d{i}" for i in range(N)]
    bench = flat()
    closes = {
        "UP": flat(100.0, N - 1) + [200.0],
        "FLAT": flat(),
        "DOWN": flat(100.0, N - 1) + [50.0],
        "NEW": [None] * (N - 10) + flat(100.0, 10),  # listed 10 days ago
    }
    rows = {r["ticker"]: r for r in rs.compute_ratings(dates, bench, closes)}
    assert set(rows) == {"UP", "FLAT", "DOWN"}
    assert rows["UP"]["rs_rating"] == 99
    assert rows["DOWN"]["rs_rating"] == 1
    assert rows["UP"]["rs_score"] == pytest.approx(200.0)
    assert rows["UP"]["ret_12m"] == pytest.approx(1.0)
    assert all(r["date"] == f"d{N - 1}" for r in rows.values())
