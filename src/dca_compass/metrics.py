"""行情与估值指标。

约定：
- 价格类（最新价、200 日均线、52 周高点）用收盘价 close，与行情网站一致；
- 收益类（涨跌幅、历史最大回撤）用复权价 adj_close，包含分红。
"""

import pandas as pd

from .config import Symbol
from .storage import Storage

RETURN_PERIODS = {
    "ret_1w": pd.DateOffset(weeks=1),
    "ret_1m": pd.DateOffset(months=1),
    "ret_1y": pd.DateOffset(years=1),
}


def period_return(s: pd.Series, offset: pd.DateOffset) -> float:
    """最新值相对 offset 之前（含当天，取最近一个交易日）的涨跌幅。"""
    past = s[: s.index[-1] - offset]
    return s.iloc[-1] / past.iloc[-1] - 1 if len(past) else float("nan")


def max_drawdown(s: pd.Series) -> tuple[float, pd.Timestamp | None]:
    """历史最大回撤（负数）及谷底日期。"""
    dd = s / s.cummax() - 1
    return float(dd.min()), dd.idxmin()


def price_metrics(prices: pd.DataFrame) -> dict:
    close, adj = prices["close"].dropna(), prices["adj_close"].dropna()
    last = close.index[-1]
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else float("nan")
    high_52w = close[last - pd.DateOffset(weeks=52):].max()
    mdd, mdd_date = max_drawdown(adj)
    return {
        "date": last,
        "price": close.iloc[-1],
        "ret_1d": adj.iloc[-1] / adj.iloc[-2] - 1 if len(adj) > 1 else float("nan"),
        **{k: period_return(adj, off) for k, off in RETURN_PERIODS.items()},
        "ma200": ma200,
        "ma200_dev": close.iloc[-1] / ma200 - 1,
        "high_52w": high_52w,
        "dd_52w": close.iloc[-1] / high_52w - 1,
        "max_dd": mdd,
        "max_dd_date": mdd_date,
    }


def percentile_rank(history: pd.Series, current: float) -> float:
    """current 在 history 中的分位（0~1，越低越便宜）。"""
    history = history.dropna()
    if pd.isna(current) or history.empty:
        return float("nan")
    return float((history <= current).mean())


def valuation_metrics(vals: pd.DataFrame, years: int, min_samples: int) -> dict:
    out = {"pe": float("nan"), "forward_pe": float("nan"), "pe_pct": float("nan"), "pe_samples": 0}
    if vals.empty:
        return out
    latest = vals.iloc[-1]
    window = vals.loc[vals.index[-1] - pd.DateOffset(years=years):, "pe"].dropna()
    out.update(pe=latest["pe"], forward_pe=latest["forward_pe"], pe_samples=len(window))
    if len(window) >= min_samples:
        out["pe_pct"] = percentile_rank(window, latest["pe"])
    return out


def compute_all(store: Storage, watchlist: list[Symbol], settings: dict) -> pd.DataFrame:
    """每个标的一行的指标表，没有行情的标的跳过。"""
    v = settings.get("valuation", {})
    years, min_samples = v.get("history_years", 5), v.get("min_samples", 20)
    rows = []
    for s in watchlist:
        prices = store.load_prices(s.symbol)
        if prices.empty:
            continue
        rows.append({
            "symbol": s.symbol, "kind": s.kind, "sector": s.sector, "name": s.name,
            **price_metrics(prices),
            **valuation_metrics(store.load_valuations(s.symbol), years, min_samples),
        })
    return pd.DataFrame(rows).set_index("symbol")
