import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dca_compass.dashboard import data
from dca_compass.metrics import price_metrics, valuation_metrics

st.title("详情")
data.require_data()

info = data.symbol_info()
tx, _ = data.transactions()
options = list(dict.fromkeys([*info.index, *tx["symbol"].unique()]))

# 选中的标的：URL ?symbol= 优先，其次是观察页点击，默认第一个
qp = st.query_params.get("symbol", "").upper()
if qp in options:
    st.session_state["detail_symbol"] = qp
elif st.session_state.get("detail_symbol") not in options:
    st.session_state["detail_symbol"] = options[0]


def sync_url():
    st.query_params["symbol"] = st.session_state["detail_symbol"]


def label(sym: str) -> str:
    if sym not in info.index:
        return f"{sym}（买入记录）"
    r = info.loc[sym]
    extra = r["name"] if isinstance(r["name"], str) else r["sector"]
    return f"{sym} · {r['kind_label']} · {extra}"


c = st.columns([3, 3, 1])
sym = c[0].selectbox("标的", options, key="detail_symbol", format_func=label, on_change=sync_url)
st.query_params["symbol"] = sym
RANGES = {"1年": 1, "3年": 3, "5年": 5, "10年": 10, "全部": None}
rng = c[1].segmented_control("区间", list(RANGES), default="3年") or "3年"
log_y = c[2].toggle("对数坐标")

p = data.prices(sym)
if p.empty:
    st.warning(f"{sym} 没有行情数据，运行 `uv run dca-update --symbols {sym}`。")
    st.stop()

# 关键指标
settings = data.settings()
v = settings.get("valuation", {})
pm = price_metrics(p)
vm = valuation_metrics(data.valuations(sym), v.get("history_years", 5), v.get("min_samples", 20))
pct = lambda x: "—" if pd.isna(x) else f"{x:+.1%}"
k = st.columns(6)
k[0].metric("现价", f"${pm['price']:,.2f}", pct(pm["ret_1d"]), help=f"{pm['date']:%Y-%m-%d} 收盘")
k[1].metric("年涨跌", pct(pm["ret_1y"]))
k[2].metric("距52周高点", pct(pm["dd_52w"]), help=f"52 周高点 ${pm['high_52w']:,.2f}")
k[3].metric("偏离200日线", pct(pm["ma200_dev"]))
k[4].metric("历史最大回撤", pct(pm["max_dd"]), help=f"谷底 {pm['max_dd_date']:%Y-%m-%d}")
k[5].metric(
    "PE / 分位",
    "—" if pd.isna(vm["pe"]) else f"{vm['pe']:.1f}",
    None if pd.isna(vm["pe_pct"]) else f"分位 {vm['pe_pct']:.0%}",
    delta_color="off",
    help=f"估值快照 {vm['pe_samples']} 天" + ("" if pd.isna(vm["forward_pe"]) else f"；远期 PE {vm['forward_pe']:.1f}"),
)

m = data.metrics()
if sym in m.index and m.loc[sym, "reasons"]:
    tag = "可考虑加码" if m.loc[sym, "consider_add"] else "提示"
    st.info(f"**{tag}**：{m.loc[sym, 'reasons']}")

# 价格 + 200 日均线 + 买入点
ma200 = p["close"].rolling(200).mean()
years = RANGES[rng]
start = p.index[-1] - pd.DateOffset(years=years) if years else p.index[0]
view, ma_view = p.loc[start:], ma200.loc[start:]
buys = tx[(tx["symbol"] == sym) & (tx["date"] >= start)]

fig = go.Figure()
fig.add_scatter(x=view.index, y=view["close"], name="收盘价", line=dict(color=data.BLUE, width=2),
                hovertemplate="$%{y:,.2f}")
fig.add_scatter(x=ma_view.index, y=ma_view, name="200日均线", line=dict(color=data.ORANGE, width=2),
                hovertemplate="$%{y:,.2f}")
if not buys.empty:
    fig.add_scatter(
        x=buys["date"], y=buys["price"], name="我的买入", mode="markers",
        marker=dict(symbol="triangle-up", size=12, color=data.AQUA, line=dict(width=1.5, color="white")),
        customdata=buys[["cost", "shares"]].values,
        hovertemplate="$%{y:,.2f}，投入 $%{customdata[0]:,.0f}，%{customdata[1]:.4f} 份",
    )

holdings, _, _ = data.portfolio()
held = sym in holdings.index
if held:
    avg = holdings.loc[sym, "avg_cost"]
    fig.add_hline(y=avg, line=dict(color=data.GRAY, width=1.5, dash="dash"),
                  annotation_text=f"平均成本 ${avg:,.2f}", annotation_position="bottom right")

fig.update_layout(
    height=480, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
    yaxis=dict(type="log" if log_y else "linear", tickprefix="$", gridcolor="rgba(128,128,128,0.15)"),
    xaxis=dict(showgrid=False),
)
st.plotly_chart(fig, width="stretch")

# 我的持仓
if held:
    st.subheader("我的持仓")
    h = holdings.loc[sym]
    k = st.columns(6)
    k[0].metric("份额", f"{h['shares']:.4f}")
    k[1].metric("平均成本", f"${h['avg_cost']:,.2f}")
    k[2].metric("投入", f"${h['invested']:,.0f}")
    k[3].metric("市值", f"${h['market_value']:,.0f}")
    k[4].metric("收益率", f"{h['return']:+.2%}")
    k[5].metric("XIRR", f"{h['xirr']:.2%}")
    st.dataframe(
        tx[tx["symbol"] == sym].sort_values("date", ascending=False)[["date", "amount", "price", "shares", "fee"]],
        column_config={
            "date": st.column_config.DateColumn("日期"),
            "amount": st.column_config.NumberColumn("金额", format="dollar"),
            "price": st.column_config.NumberColumn("价格", format="dollar"),
            "shares": st.column_config.NumberColumn("份额", format="%.4f"),
            "fee": st.column_config.NumberColumn("手续费", format="dollar"),
        },
        hide_index=True, width="stretch",
    )

# 估值历史
vals = data.valuations(sym)
st.subheader("PE 历史")
if len(vals) >= 2:
    fv = go.Figure()
    fv.add_scatter(x=vals.index, y=vals["pe"], name="PE", line=dict(color=data.BLUE, width=2))
    if vals["forward_pe"].notna().any():
        fv.add_scatter(x=vals.index, y=vals["forward_pe"], name="远期 PE", line=dict(color=data.ORANGE, width=2))
    fv.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified",
                     legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
    st.plotly_chart(fv, width="stretch")
else:
    st.caption(f"目前只有 {len(vals)} 天的估值快照。每天运行 `dca-update` 会积累一份，用于计算历史分位。")
