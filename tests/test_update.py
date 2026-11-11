from datetime import date, timedelta

import pandas as pd
import pytest

from dca_compass.providers.base import PRICE_COLUMNS
from dca_compass.storage import Storage
from dca_compass.update import run, update_prices, with_retry

START = date(2024, 1, 1)


def make_df(days: list[date], close: float = 100.0, action_on: date | None = None) -> pd.DataFrame:
    df = pd.DataFrame({c: close for c in PRICE_COLUMNS}, index=pd.Index(days, name="date"))
    df["has_action"] = [d == action_on for d in days]
    return df


class FakeProvider:
    """按日期区间返回预设行情，可设置前几次调用失败。"""

    def __init__(self, days, fail_times=0, action_on=None):
        self.days, self.fail_times, self.action_on = days, fail_times, action_on
        self.calls = []

    def get_history(self, symbol, start=None):
        self.calls.append(start)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError("network down")
        days = [d for d in self.days if start is None or d >= start]
        return make_df(days, action_on=self.action_on)

    def get_valuation(self, symbol):
        return {"pe": 20.0, "forward_pe": 18.0}


def days(n, first=START):
    return [first + timedelta(days=i) for i in range(n)]


def test_first_run_is_full_then_incremental():
    store = Storage(":memory:")
    p = FakeProvider(days(10))
    assert update_prices(store, p, "SPY", START) == "全量 10 天"

    p.days = days(13)
    assert update_prices(store, p, "SPY", START) == "新增 3 天"
    assert p.calls[-1] == START + timedelta(days=9 - 7)  # 带重叠窗口
    assert len(store.load_prices("SPY")) == 13


def test_dividend_triggers_full_refresh():
    store = Storage(":memory:")
    p = FakeProvider(days(10))
    update_prices(store, p, "SPY", START)

    p.days, p.action_on = days(12), START + timedelta(days=11)
    assert "分红" in update_prices(store, p, "SPY", START)
    assert p.calls[-1] == START


def flaky(fail_times):
    state = {"n": 0}

    def fn():
        state["n"] += 1
        if state["n"] <= fail_times:
            raise ValueError("boom")
        return "ok"

    return fn


def test_retry():
    no_sleep = lambda s: None
    assert with_retry(flaky(2), retries=3, sleep=no_sleep) == "ok"
    with pytest.raises(ValueError):
        with_retry(flaky(3), retries=3, sleep=no_sleep)


def test_run_reports_failures_and_saves_valuation():
    store = Storage(":memory:")
    ok = run(["SPY"], store, FakeProvider(days(5), fail_times=2), START, retries=3, sleep=lambda s: None)
    assert ok == []
    assert store.load_valuations("SPY")["pe"].iloc[0] == 20.0

    failed = run(["QQQ"], store, FakeProvider(days(5), fail_times=5), START, retries=3, sleep=lambda s: None)
    assert failed == ["QQQ"]
