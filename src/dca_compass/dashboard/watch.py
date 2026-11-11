import pandas as pd
import streamlit as st

from dca_compass.dashboard import data

st.title("观察")
data.require_data()

m = data.metrics()
rules = data.settings().get("signals", {})

# 筛选和排序放在一行
SORTS = {
    "距52周高点回撤（深→浅）": ("dd_52w", True),
    "PE 分位（低→高）": ("pe_pct", True),
    "200日线偏离（低→高）": ("ma200_dev", True),
    "年涨跌幅（低→高）": ("ret_1y", True),
    "历史最大回撤（深→浅）": ("max_dd", True),
}
c = st.columns([2, 2, 3, 1.4])
kinds = c[0].multiselect("类型", list(data.KIND_LABELS.values()), placeholder="全部")
sectors = c[1].multiselect("行业", sorted(m["sector"].dropna().unique()), placeholder="全部")
sort_label = c[2].selectbox("排序", list(SORTS))
only_flagged = c[3].toggle("只看加码提示")

view = m
if kinds:
    view = view[view["kind_label"].isin(kinds)]
if sectors:
    view = view[view["sector"].isin(sectors)]
if only_flagged:
    view = view[view["consider_add"]]
col, asc = SORTS[sort_label]
view = view.sort_values(col, ascending=asc, na_position="last")

COLUMNS = {
    "kind_label": "类型", "sector": "行业", "price": "现价",
    "ret_1d": "日", "ret_1w": "周", "ret_1m": "月", "ret_1y": "年",
    "ma200_dev": "偏离200日线", "dd_52w": "距52周高点", "max_dd": "最大回撤",
    "pe": "PE", "forward_pe": "远期PE", "pe_pct": "PE分位", "reasons": "提示",
}
PCT = ["ret_1d", "ret_1w", "ret_1m", "ret_1y", "ma200_dev", "dd_52w", "max_dd", "pe_pct"]

# 高亮：触发加码阈值的单元格用蓝色，低于200日线用浅黄色；“提示”列给出文字原因
ADD = "background-color: rgba(42, 120, 214, 0.22)"
WEAK = "background-color: rgba(250, 178, 25, 0.18)"


def highlight(df: pd.DataFrame) -> pd.DataFrame:
    flags = view.loc[df.index]
    s = pd.DataFrame("", index=df.index, columns=df.columns)
    s.loc[flags["dd_flag"], "dd_52w"] = ADD
    s.loc[flags["val_flag"], "pe_pct"] = ADD
    s.loc[flags["below_ma200"], "ma200_dev"] = WEAK
    return s


def color_sign(v):
    if pd.isna(v) or v == 0:
        return ""
    return "color: #0ca30c" if v > 0 else "color: #d03b3b"


table = view[list(COLUMNS)].fillna({"sector": "—"})
styler = (
    table.style
    .apply(highlight, axis=None)
    .map(color_sign, subset=["ret_1d", "ret_1w", "ret_1m", "ret_1y"])
    .format("{:.1%}", subset=PCT, na_rep="—")
    .format("{:.1f}", subset=["pe", "forward_pe"], na_rep="—")
    .format("${:,.2f}", subset=["price"])
)

st.caption(
    f"共 {len(view)} 个标的。蓝底：触发加码阈值（回撤 ≥ {rules.get('drawdown_from_high', 0):.0%} "
    f"或 PE 分位 ≤ {rules.get('valuation_percentile', 0):.0%}）；黄底：低于 200 日线。点选一行可查看详情。"
)
event = st.dataframe(
    styler,
    column_config={"_index": "代码", **{k: st.column_config.Column(v) for k, v in COLUMNS.items()}},
    width="stretch",
    height=min(38 * len(view) + 40, 900),
    on_select="rerun",
    selection_mode="single-row",
)

if event.selection.rows:
    sym = view.index[event.selection.rows[0]]
    st.session_state["detail_symbol"] = sym
    st.switch_page(data.PAGE_DETAIL)

samples = int(m["pe_samples"].max()) if "pe_samples" in m else 0
min_samples = data.settings().get("valuation", {}).get("min_samples", 20)
if samples < min_samples:
    st.caption(f"PE 分位需要至少 {min_samples} 天的估值快照，目前最多 {samples} 天；每天运行 `dca-update` 会自动积累。")
