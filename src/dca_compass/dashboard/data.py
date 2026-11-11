"""看板共用的数据加载（带缓存）。"""

from datetime import date

import pandas as pd
import streamlit as st

from ..config import CONFIG_DIR, db_path, load_settings, load_watchlist, transactions_path
from ..metrics import compute_all
from ..portfolio import latest_prices, load_transactions, summarize
from ..signals import add_flags, dca_reminder
from ..storage import Storage

PAGE_DETAIL = "detail.py"  # 相对 app.py，用于 st.switch_page

KIND_LABELS ={"index": "指数 ETF", "sector": "行业 ETF", "stock": "个股"}

# 参考配色（dataviz 默认色板）
BLUE, ORANGE, AQUA, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984"


def _store() -> Storage:
    return Storage(db_path())


@st.cache_data(ttl=600)
def settings() -> dict:
    return load_settings()


@st.cache_data(ttl=600)
def symbol_info() -> pd.DataFrame:
    df = pd.DataFrame([s.__dict__ for s in load_watchlist()]).set_index("symbol")
    df["kind_label"] = df["kind"].map(KIND_LABELS)
    return df


@st.cache_data(ttl=600)
def metrics() -> pd.DataFrame:
    table = compute_all(_store(), load_watchlist(), settings())
    if table.empty:
        return table
    table = add_flags(table, settings().get("signals", {}))
    table["kind_label"] = table["kind"].map(KIND_LABELS)
    return table


@st.cache_data(ttl=600)
def transactions() -> tuple[pd.DataFrame, bool]:
    """返回 (买入记录, 是否为示例文件)。"""
    path = transactions_path()
    return load_transactions(path), path.parent == CONFIG_DIR and path.name.endswith(".example.csv")


@st.cache_data(ttl=600)
def portfolio() -> tuple[pd.DataFrame, dict, date | None]:
    tx, _ = transactions()
    prices, as_of = latest_prices(_store(), tx["symbol"].unique())
    table, total = summarize(tx, prices, as_of or date.today())
    return table, total, as_of


@st.cache_data(ttl=600)
def reminder() -> dict:
    tx, _ = transactions()
    return dca_reminder(date.today(), settings().get("dca_plan", {}), tx)


@st.cache_data(ttl=600)
def prices(symbol: str) -> pd.DataFrame:
    return _store().load_prices(symbol)


@st.cache_data(ttl=600)
def valuations(symbol: str) -> pd.DataFrame:
    return _store().load_valuations(symbol)


def require_data() -> None:
    """没有行情数据时提示并停止渲染。"""
    if not db_path().exists() or metrics().empty:
        st.warning("还没有行情数据。请先在终端运行 `uv run dca-update`。")
        st.stop()
