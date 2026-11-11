import streamlit as st

from dca_compass.dashboard import data

st.title("总览")
data.require_data()

# 定投提醒
r = data.reminder()
pending = [a for a in r["allocations"] if not a["bought_this_month"]]
overdue = [a["symbol"] for a in r["allocations"] if a["overdue"]]
msg = f"下一个定投日 **{r['next_date']:%Y-%m-%d}**（{r['days_until']} 天后）"
if overdue:
    st.error(f"⚠️ 本月定投逾期未买：{'、'.join(overdue)}。{msg}")
elif r["remind"] and pending:
    st.warning(f"⏰ {msg}，待买：" + "、".join(f"{a['symbol']} ${a['amount']:,.0f}" for a in pending))
else:
    st.info(f"🗓️ {msg}")

# 组合汇总
tx, is_example = data.transactions()
table, total, as_of = data.portfolio()
if is_example:
    st.caption("当前显示的是示例记录。复制 `config/transactions.example.csv` 为 `config/transactions.csv` 后填入自己的买入。")

if not total:
    st.info("还没有买入记录。")
    st.stop()

c = st.columns(4)
c[0].metric("市值", f"${total['market_value']:,.0f}")
c[1].metric("累计投入", f"${total['invested']:,.0f}", help=f"{total['n_buys']} 笔，首笔 {total['first_buy']:%Y-%m-%d}")
c[2].metric("收益", f"${total['pnl']:+,.0f}", f"{total['return']:+.2%}")
c[3].metric("XIRR（年化）", f"{total['xirr']:.2%}")
if total["missing_prices"]:
    st.warning(f"以下标的缺少行情，未计入合计：{'、'.join(total['missing_prices'])}。运行 `uv run dca-update` 补齐。")
st.caption(f"估值日：{as_of}")

st.subheader("持仓")
st.dataframe(
    table.sort_values("market_value", ascending=False)[
        ["weight", "shares", "avg_cost", "price", "invested", "market_value", "pnl", "return", "xirr", "n_buys"]
    ],
    column_config={
        "_index": "代码",
        "weight": st.column_config.ProgressColumn("占比", format="percent", min_value=0, max_value=1),
        "shares": st.column_config.NumberColumn("份额", format="%.4f"),
        "avg_cost": st.column_config.NumberColumn("平均成本", format="dollar"),
        "price": st.column_config.NumberColumn("现价", format="dollar"),
        "invested": st.column_config.NumberColumn("投入", format="dollar"),
        "market_value": st.column_config.NumberColumn("市值", format="dollar"),
        "pnl": st.column_config.NumberColumn("收益", format="dollar"),
        "return": st.column_config.NumberColumn("收益率", format="percent"),
        "xirr": st.column_config.NumberColumn("XIRR", format="percent"),
        "n_buys": st.column_config.NumberColumn("买入次数"),
    },
    width="stretch",
)

# 加码提示
m = data.metrics()
flagged = m[m["consider_add"]].sort_values("dd_52w")
st.subheader(f"可考虑加码（{len(flagged)}）")
if flagged.empty:
    st.caption("当前没有标的触发阈值。")
else:
    st.dataframe(
        flagged[["kind_label", "sector", "price", "reasons"]],
        column_config={
            "_index": "代码", "kind_label": "类型", "sector": "行业",
            "price": st.column_config.NumberColumn("现价", format="dollar"),
            "reasons": "原因",
        },
        width="stretch",
    )
st.caption("仅为提示，不构成交易建议。阈值在 `config/settings.yaml` 中设置。")
