import math

import pandas as pd
import pytest

from dca_compass.config import Symbol
from dca_compass.metrics import (
    compute_all, max_drawdown, percentile_rank, period_return, price_metrics, valuation_metrics,
)
from dca_compass.storage import Storage


def series(values, start="2024-01-01", freq="D"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=freq), dtype=float)


def prices_df(close, adj=None):
    return pd.DataFrame({"close": close, "adj_close": close if adj is None else adj})


def test_period_return_uses_last_day_on_or_before_offset():
    s = series(range(100, 111))  # 2024-01-01 .. 2024-01-11，每天 +1
    assert period_return(s, pd.DateOffset(weeks=1)) == pytest.approx(110 / 103 - 1)
    assert math.isnan(period_return(s, pd.DateOffset(years=1)))  # 历史不够长


def test_max_drawdown():
    mdd, when = max_drawdown(series([100, 120, 60, 90, 130]))
    assert mdd == pytest.approx(-0.5)
    assert when == pd.Timestamp("2024-01-03")


def test_price_metrics_ma200_and_52w_drawdown():
    # 300 天：前 250 天从 1 涨到 250，之后跌到 200
    values = list(range(1, 251)) + [250 - i for i in range(1, 51)]
    m = price_metrics(prices_df(series(values)))
    assert m["price"] == 200
    assert m["ret_1d"] == pytest.approx(200 / 201 - 1)
    assert m["ma200"] == pytest.approx(sum(values[-200:]) / 200)
    assert m["ma200_dev"] == pytest.approx(200 / m["ma200"] - 1)
    assert m["high_52w"] == 250
    assert m["dd_52w"] == pytest.approx(-0.2)
    assert m["max_dd"] == pytest.approx(-0.2)


def test_returns_use_adjusted_price_and_levels_use_close():
    close = series([100.0] * 10)
    adj = series([90.0] * 9 + [100.0])  # 复权价包含分红
    m = price_metrics(prices_df(close, adj))
    assert m["price"] == 100
    assert m["ret_1d"] == pytest.approx(100 / 90 - 1)
    assert m["dd_52w"] == 0
    assert math.isnan(m["ma200"])  # 不足 200 天


def test_percentile_rank():
    hist = series([10, 20, 30, 40, 50])
    assert percentile_rank(hist, 10) == pytest.approx(0.2)
    assert percentile_rank(hist, 50) == 1.0
    assert percentile_rank(hist, 5) == 0.0
    assert math.isnan(percentile_rank(hist, float("nan")))


def test_valuation_metrics_window_and_min_samples():
    pe = series([100] * 5 + list(range(10, 30)), start="2015-01-01", freq="180D")
    vals = pd.DataFrame({"pe": pe, "forward_pe": pe * 0.9})
    m = valuation_metrics(vals, years=5, min_samples=5)
    # 只看最近 5 年，早年的 100 不在窗口内；最新值 29 是窗口内最高
    assert m["pe"] == 29
    assert m["pe_pct"] == 1.0
    assert m["pe_samples"] == 11

    assert math.isnan(valuation_metrics(vals, years=5, min_samples=50)["pe_pct"])
    assert math.isnan(valuation_metrics(vals.iloc[:0], 5, 1)["pe"])


def test_compute_all_skips_symbols_without_data():
    store = Storage(":memory:")
    df = prices_df(series([1.0, 2.0, 3.0]))
    for c in ["open", "high", "low", "volume"]:
        df[c] = 1.0
    store.upsert_prices("SPY", df)
    table = compute_all(store, [Symbol("SPY", "index"), Symbol("QQQ", "index")], {})
    assert list(table.index) == ["SPY"]
    assert table.loc["SPY", "price"] == 3
