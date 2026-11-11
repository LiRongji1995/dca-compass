import io
import math
from datetime import date

import pytest

from dca_compass.config import CONFIG_DIR
from dca_compass.portfolio import load_transactions, summarize, xirr

CSV = """date,symbol,amount,price,shares,fee
2023-01-01,aaa,100,10,10,1
2023-07-01,AAA,200,20,,
2023-01-01,BBB,,50,2,0
"""


def tx():
    return load_transactions(io.StringIO(CSV))


def test_load_fills_missing_fields():
    t = tx()
    assert list(t["symbol"]) == ["AAA", "BBB", "AAA"]  # 大写并按日期排序
    assert t.loc[2, "shares"] == 10  # 200 / 20
    assert t.loc[1, "amount"] == 100  # 50 * 2
    assert list(t["cost"]) == [101, 100, 200]  # 含手续费


def test_load_rejects_bad_rows():
    with pytest.raises(ValueError, match="行号"):
        load_transactions(io.StringIO("date,symbol,amount,price,shares,fee\n2023-01-01,AAA,,,,\n"))


def test_example_file_loads():
    assert len(load_transactions(CONFIG_DIR / "transactions.example.csv")) > 0


def test_xirr_simple_one_year():
    assert xirr([(date(2021, 1, 1), -1000), (date(2022, 1, 1), 1100)]) == pytest.approx(0.10)


def test_xirr_matches_excel_example():
    # Excel 文档中的 XIRR 示例，结果 0.373362535
    flows = [
        (date(2008, 1, 1), -10000), (date(2008, 3, 1), 2750), (date(2008, 10, 30), 4250),
        (date(2009, 2, 15), 3250), (date(2009, 4, 1), 2750),
    ]
    assert xirr(flows) == pytest.approx(0.373362535, abs=1e-6)


def test_xirr_no_solution():
    assert math.isnan(xirr([(date(2021, 1, 1), -100), (date(2022, 1, 1), -100)]))
    assert math.isnan(xirr([]))


def test_summarize_per_symbol_and_total():
    table, total = summarize(tx(), {"AAA": 25, "BBB": 40}, date(2024, 1, 1))

    a = table.loc["AAA"]
    assert a["shares"] == 20
    assert a["invested"] == 301
    assert a["avg_cost"] == pytest.approx(15.05)
    assert a["market_value"] == 500
    assert a["pnl"] == 199
    assert a["return"] == pytest.approx(500 / 301 - 1)

    b = table.loc["BBB"]
    assert b["return"] == pytest.approx(-0.2)
    assert b["xirr"] == pytest.approx(-0.2)  # 正好持有 365 天

    assert table["weight"].sum() == pytest.approx(1)
    assert total["invested"] == 401
    assert total["market_value"] == 580
    assert total["missing_prices"] == []
    # 组合 XIRR 应介于两个标的之间
    assert b["xirr"] < total["xirr"] < a["xirr"]


def test_summarize_missing_price_excluded_from_total():
    table, total = summarize(tx(), {"AAA": 25}, date(2024, 1, 1))
    assert math.isnan(table.loc["BBB", "market_value"])
    assert total["missing_prices"] == ["BBB"]
    assert total["invested"] == 301
    assert table.loc["AAA", "weight"] == 1
