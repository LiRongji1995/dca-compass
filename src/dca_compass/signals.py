"""提示规则：定投日提醒、“可考虑加码”标记。只做提示，不自动交易。"""

import calendar
from datetime import date, timedelta

import pandas as pd


def dca_date(year: int, month: int, day: int) -> date:
    """某月的定投日：超出月末取月末，落在周末顺延到周一（不处理节假日）。"""
    d = date(year, month, min(day, calendar.monthrange(year, month)[1]))
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def dca_reminder(today: date, plan: dict, tx: pd.DataFrame | None = None) -> dict:
    """返回下一个定投日、距离天数、是否该提醒，以及本月各标的是否已买。"""
    day = plan.get("day_of_month", 1)
    this_month = dca_date(today.year, today.month, day)
    if today <= this_month:
        next_date = this_month
    else:
        y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        next_date = dca_date(y, m, day)
    days_until = (next_date - today).days

    bought = set()
    if tx is not None and not tx.empty:
        month_tx = tx[(tx["date"].dt.year == today.year) & (tx["date"].dt.month == today.month)]
        bought = set(month_tx["symbol"])
    allocations = [
        {"symbol": s, "amount": a, "bought_this_month": s in bought,
         "overdue": today > this_month and s not in bought}
        for s, a in (plan.get("allocations") or {}).items()
    ]
    return {
        "next_date": next_date,
        "days_until": days_until,
        "remind": days_until <= plan.get("remind_days_before", 0),
        "allocations": allocations,
    }


def add_flags(metrics: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """在指标表上加标记列：dd_flag / val_flag / below_ma200 / consider_add / reasons。"""
    m = metrics.copy()
    dd_th = rules.get("drawdown_from_high")
    pct_th = rules.get("valuation_percentile")

    m["dd_flag"] = (m["dd_52w"] <= -dd_th) if dd_th is not None else False
    m["val_flag"] = (m["pe_pct"] <= pct_th) if pct_th is not None else False
    m["below_ma200"] = (m["ma200_dev"] < 0) if rules.get("below_ma200") else False
    m["consider_add"] = m["dd_flag"] | m["val_flag"]

    def reasons(r) -> str:
        out = []
        if r["dd_flag"]:
            out.append(f"距52周高点 {r['dd_52w']:.0%}")
        if r["val_flag"]:
            out.append(f"PE 分位 {r['pe_pct']:.0%}")
        if r["below_ma200"]:
            out.append(f"低于200日线 {r['ma200_dev']:.0%}")
        return "；".join(out)

    m["reasons"] = m.apply(reasons, axis=1) if len(m) else pd.Series(dtype=str)
    return m


def main() -> None:
    from .config import db_path, load_settings, load_watchlist, transactions_path
    from .metrics import compute_all
    from .portfolio import load_transactions
    from .storage import Storage

    settings = load_settings()
    r = dca_reminder(date.today(), settings.get("dca_plan", {}), load_transactions(transactions_path()))
    print(f"下一个定投日: {r['next_date']}（{r['days_until']} 天后）" + ("  ← 该准备定投了" if r["remind"] else ""))
    for a in r["allocations"]:
        status = "本月已买" if a["bought_this_month"] else ("逾期未买" if a["overdue"] else "待买")
        print(f"  {a['symbol']:6} ${a['amount']:>8,.0f}  {status}")

    flagged = add_flags(compute_all(Storage(db_path()), load_watchlist(), settings), settings.get("signals", {}))
    flagged = flagged[flagged["consider_add"]].sort_values("dd_52w")
    print(f"\n可考虑加码（{len(flagged)}）:")
    for sym, row in flagged.iterrows():
        print(f"  {sym:6} {row['reasons']}")


if __name__ == "__main__":
    main()
