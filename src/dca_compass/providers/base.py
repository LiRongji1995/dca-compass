"""数据源接口。换数据源只需实现这两个方法。"""

from datetime import date
from typing import Protocol

import pandas as pd

PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


class PriceProvider(Protocol):
    def get_history(self, symbol: str, start: date | None = None) -> pd.DataFrame:
        """返回日线，索引为 date，列为 PRICE_COLUMNS，另加 has_action（当日有分红/拆股）。
        没有数据时返回空表；网络等错误直接抛异常。"""
        ...

    def get_valuation(self, symbol: str) -> dict:
        """返回当前估值 {"pe": float|None, "forward_pe": float|None}。"""
        ...
