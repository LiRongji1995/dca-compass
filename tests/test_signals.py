from datetime import date

import pandas as pd

from dca_compass.signals import add_flags, dca_date, dca_reminder

PLAN = {"day_of_month": 15, "remind_days_before": 2, "allocations": {"VTI": 500, "QQQ": 300}}


def test_dca_date_weekend_and_month_end():
    assert dca_date(2024, 6, 15) == date(2024, 6, 17)  # 周六 -> 周一
    assert dca_date(2024, 2, 31) == date(2024, 2, 29)  # 超出月末
    assert dca_date(2024, 5, 15) == date(2024, 5, 15)  # 工作日不变


def test_reminder_window():
    r = dca_reminder(date(2024, 5, 13), PLAN)
    assert r["next_date"] == date(2024, 5, 15)
    assert r["days_until"] == 2 and r["remind"]

    r = dca_reminder(date(2024, 5, 10), PLAN)
    assert not r["remind"]

    r = dca_reminder(date(2024, 5, 15), PLAN)
    assert r["days_until"] == 0 and r["remind"]


def test_reminder_rolls_to_next_month_and_year():
    assert dca_reminder(date(2024, 5, 16), PLAN)["next_date"] == date(2024, 6, 17)
    assert dca_reminder(date(2024, 12, 20), PLAN)["next_date"] == date(2025, 1, 15)


def test_bought_and_overdue():
    tx = pd.DataFrame({"date": pd.to_datetime(["2024-05-15", "2024-04-15"]), "symbol": ["VTI", "QQQ"]})
    r = dca_reminder(date(2024, 5, 20), PLAN, tx)
    status = {a["symbol"]: a for a in r["allocations"]}
    assert status["VTI"]["bought_this_month"] and not status["VTI"]["overdue"]
    assert not status["QQQ"]["bought_this_month"] and status["QQQ"]["overdue"]

    # 定投日之前不算逾期
    r = dca_reminder(date(2024, 5, 10), PLAN, tx)
    assert not any(a["overdue"] for a in r["allocations"])


def test_add_flags():
    metrics = pd.DataFrame(
        {"dd_52w": [-0.20, -0.05, -0.05, -0.30],
         "pe_pct": [0.50, 0.10, float("nan"), 0.05],
         "ma200_dev": [-0.1, 0.02, 0.01, -0.2]},
        index=["A", "B", "C", "D"],
    )
    rules = {"drawdown_from_high": 0.15, "valuation_percentile": 0.2, "below_ma200": True}
    f = add_flags(metrics, rules)
    assert list(f["consider_add"]) == [True, True, False, True]
    assert list(f["below_ma200"]) == [True, False, False, True]
    assert f.loc["A", "reasons"] == "距52周高点 -20%；低于200日线 -10%"
    assert f.loc["B", "reasons"] == "PE 分位 10%"
    assert f.loc["C", "reasons"] == ""

    f = add_flags(metrics, {})  # 没配阈值时不标记
    assert not f["consider_add"].any()
