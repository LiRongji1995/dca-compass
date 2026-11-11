"""定投记录：成本、市值、收益率、XIRR。

CSV 列：date,symbol,amount,price,shares,fee
- amount 为成交金额（不含手续费），总投入 = amount + fee
- amount 和 shares 可只填一个，另一个按 price 推算
"""

from datetime import date
from pathlib import Path

import pandas as pd
from scipy.optimize import brentq

from .storage import Storage


def load_transactions(path: Path | str) -> pd.DataFrame:
    tx = pd.read_csv(path, parse_dates=["date"], dtype={"symbol": str})
    tx["symbol"] = tx["symbol"].str.strip().str.upper()
    tx["fee"] = tx["fee"].fillna(0.0)
    tx["shares"] = tx["shares"].fillna(tx["amount"] / tx["price"])
    tx["amount"] = tx["amount"].fillna(tx["price"] * tx["shares"])
    bad = tx[tx[["date", "symbol", "amount", "shares"]].isna().any(axis=1) | (tx["shares"] <= 0)]
    if not bad.empty:
        raise ValueError(f"买入记录有误（缺字段或份额 <= 0），行号: {[i + 2 for i in bad.index]}")
    tx["cost"] = tx["amount"] + tx["fee"]
    return tx.sort_values("date").reset_index(drop=True)


def xirr(cashflows: list[tuple[date, float]]) -> float:
    """年化内部收益率（实际天数/365）。投入为负、回收为正。无解时返回 NaN。"""
    if not cashflows:
        return float("nan")
    t0 = min(pd.Timestamp(d) for d, _ in cashflows)
    flows = [((pd.Timestamp(d) - t0).days / 365.0, v) for d, v in cashflows]
    npv = lambda r: sum(v / (1 + r) ** t for t, v in flows)
    try:
        return brentq(npv, -0.9999, 100.0)
    except ValueError:  # 区间内无符号变化
        return float("nan")


def _summary(group: pd.DataFrame, value: float, as_of: date) -> dict:
    invested, shares = group["cost"].sum(), group["shares"].sum()
    flows = [(d, -c) for d, c in zip(group["date"], group["cost"])] + [(as_of, value)]
    return {
        "shares": shares,
        "invested": invested,
        "avg_cost": invested / shares,
        "market_value": value,
        "pnl": value - invested,
        "return": value / invested - 1,
        "xirr": xirr(flows) if pd.notna(value) else float("nan"),
        "first_buy": group["date"].min(),
        "n_buys": len(group),
    }


def summarize(tx: pd.DataFrame, prices: dict[str, float], as_of: date) -> tuple[pd.DataFrame, dict]:
    """返回 (每个标的一行的持仓表, 组合汇总)。缺价格的标的市值为 NaN，不计入组合。"""
    rows = {}
    for sym, g in tx.groupby("symbol"):
        price = prices.get(sym, float("nan"))
        rows[sym] = {"price": price, **_summary(g, price * g["shares"].sum(), as_of)}
    table = pd.DataFrame.from_dict(rows, orient="index")
    if table.empty:
        return table, {}

    priced = table["market_value"].notna()
    table["weight"] = table["market_value"] / table.loc[priced, "market_value"].sum()
    total = _summary(tx[tx["symbol"].isin(table.index[priced])], table.loc[priced, "market_value"].sum(), as_of)
    total["missing_prices"] = list(table.index[~priced])
    return table, total


def latest_prices(store: Storage, symbols) -> tuple[dict[str, float], date | None]:
    """各标的最新收盘价，以及其中最晚的行情日期（作为估值日）。"""
    prices, as_of = {}, None
    for sym in symbols:
        p = store.load_prices(sym)["close"].dropna()
        if not p.empty:
            prices[sym] = float(p.iloc[-1])
            as_of = max(as_of or p.index[-1], p.index[-1])
    return prices, as_of.date() if as_of is not None else None


def main() -> None:
    from .config import db_path, transactions_path

    path = transactions_path()
    tx = load_transactions(path)
    prices, as_of = latest_prices(Storage(db_path()), tx["symbol"].unique())
    table, total = summarize(tx, prices, as_of or date.today())

    print(f"记录: {path.name}    估值日: {as_of}\n")
    print(table[["shares", "avg_cost", "price", "invested", "market_value", "return", "xirr", "weight"]].round(4).to_string())
    print(f"\n累计投入 {total['invested']:,.2f}  市值 {total['market_value']:,.2f}  "
          f"收益 {total['pnl']:+,.2f} ({total['return']:+.2%})  XIRR {total['xirr']:.2%}")
    if total["missing_prices"]:
        print(f"缺少行情（先运行 dca-update）: {' '.join(total['missing_prices'])}")


if __name__ == "__main__":
    main()
