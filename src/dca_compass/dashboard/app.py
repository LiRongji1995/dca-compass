"""看板入口：uv run dca-dashboard"""

from pathlib import Path

import streamlit as st

from dca_compass.dashboard import data

HERE = Path(__file__).parent

st.set_page_config(page_title="DCA Compass", page_icon="🧭", layout="wide")

pages = [
    st.Page(HERE / "overview.py", title="总览", icon="📊", default=True),
    st.Page(HERE / "watch.py", title="观察", icon="🔭", url_path="watch"),
    st.Page(HERE / "detail.py", title="详情", icon="📈", url_path="detail"),
]
nav = st.navigation(pages)

with st.sidebar:
    m = data.metrics() if data.db_path().exists() else None
    if m is not None and not m.empty:
        st.caption(f"行情日期：{m['date'].max():%Y-%m-%d}")
    if st.button("重新加载数据", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption("更新行情：`uv run dca-update`")

nav.run()

