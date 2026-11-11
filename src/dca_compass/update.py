"""更新本地行情和估值。用法：uv run dca-update [--symbols SPY QQQ] [--full]"""

import argparse
import sys
import time
from datetime import date, timedelta

from .config import db_path, load_settings, load_watchlist, transactions_path
from .portfolio import load_transactions
from .providers import PriceProvider, get_provider
from .storage import Storage

# 增量更新时往回多取几天，覆盖上次可能未收盘的数据
OVERLAP_DAYS = 7


def with_retry(fn, retries: int, wait: float = 2.0, sleep=time.sleep):
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception:
            if attempt == retries:
                raise
            sleep(wait * attempt)


def update_prices(store: Storage, provider: PriceProvider, symbol: str,
                  start_date: date, full: bool = False) -> str:
    last = None if full else store.last_date(symbol)
    if last is not None:
        df = provider.get_history(symbol, last - timedelta(days=OVERLAP_DAYS))
        new = df[df.index > last]
        if not new["has_action"].any():
            store.upsert_prices(symbol, df)
            return f"新增 {len(new)} 天"
        # 有分红/拆股时复权价会整体变化，重新全量拉取

    df = provider.get_history(symbol, start_date)
    if df.empty:
        raise RuntimeError("数据源没有返回数据")
    n = store.upsert_prices(symbol, df, replace_all=True)
    return f"全量 {n} 天" + ("（检测到分红/拆股）" if last else "")


def update_valuation(store: Storage, provider: PriceProvider, symbol: str) -> None:
    day = store.last_date(symbol)
    if day is None:
        return
    v = provider.get_valuation(symbol)
    if v["pe"] is not None or v["forward_pe"] is not None:
        store.save_valuation(symbol, day, v["pe"], v["forward_pe"])


def run(symbols: list[str], store: Storage, provider: PriceProvider,
        start_date: date, retries: int, full: bool = False, sleep=time.sleep) -> list[str]:
    """逐个更新，返回失败的代码列表。"""
    failed = []
    for sym in symbols:
        try:
            msg = with_retry(lambda: update_prices(store, provider, sym, start_date, full), retries, sleep=sleep)
        except Exception as e:
            print(f"✗ {sym:6} 失败: {e}")
            failed.append(sym)
            continue
        try:
            with_retry(lambda: update_valuation(store, provider, sym), retries, sleep=sleep)
        except Exception as e:
            msg += f"，估值获取失败: {e}"
        print(f"✓ {sym:6} {msg}")
    return failed


def all_symbols() -> list[str]:
    """观察列表 + 买入记录里出现的代码（去重，保持顺序）。"""
    symbols = [s.symbol for s in load_watchlist()]
    symbols += list(load_transactions(transactions_path())["symbol"].unique())
    return list(dict.fromkeys(symbols))


def main() -> None:
    parser = argparse.ArgumentParser(description="更新行情和估值数据")
    parser.add_argument("--symbols", nargs="+", help="只更新这些代码（默认全部）")
    parser.add_argument("--full", action="store_true", help="忽略已有数据，全量重新拉取")
    args = parser.parse_args()

    settings = load_settings()["data"]
    symbols = args.symbols or all_symbols()
    failed = run(
        symbols,
        Storage(db_path()),
        get_provider(settings.get("provider", "yfinance")),
        date.fromisoformat(settings["start_date"]),
        settings.get("retries", 3),
        args.full,
    )
    print(f"\n完成 {len(symbols) - len(failed)}/{len(symbols)}" + (f"，失败: {' '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
