from datetime import date

import pandas as pd
import yfinance as yf

from .base import PRICE_COLUMNS


class YFinanceProvider:
    def get_history(self, symbol: str, start: date | None = None) -> pd.DataFrame:
        kwargs = {"start": start.isoformat()} if start else {"period": "max"}
        df = yf.Ticker(symbol).history(auto_adjust=False, actions=True, raise_errors=True, **kwargs)
        if df.empty:
            return pd.DataFrame(columns=PRICE_COLUMNS + ["has_action"])
        out = df.rename(columns=lambda c: c.lower().replace(" ", "_"))
        out["has_action"] = (out.get("dividends", 0) != 0) | (out.get("stock_splits", 0) != 0)
        out.index = pd.Index(df.index.date, name="date")
        return out[PRICE_COLUMNS + ["has_action"]]

    def get_valuation(self, symbol: str) -> dict:
        info = yf.Ticker(symbol).info or {}
        return {"pe": _num(info.get("trailingPE")), "forward_pe": _num(info.get("forwardPE"))}


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None  # 负 PE 无意义，按缺失处理
