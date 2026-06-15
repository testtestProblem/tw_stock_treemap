"""介面呈現：Streamlit Debug UI + Plotly Treemap。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from data.exporter import export_snapshots
from data.fetcher import ShioajiFetcher, UsageInfo
from data.universe import StockMeta, build_meta_index, category_of, load_universe


@st.cache_resource(show_spinner="登入 Shioaji 並載入商品檔...")
def get_fetcher() -> ShioajiFetcher:
    fetcher = ShioajiFetcher()
    fetcher.login()
    return fetcher


def _init_session_state() -> None:
    defaults = {
        "quotes": [],
        "missing_codes": [],
        "last_updated": None,
        "usage_info": None,
        "fetch_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _filter_universe(
    include_listed: bool,
    include_otc: bool,
    include_etf: bool,
) -> list[StockMeta]:
    return load_universe(
        include_listed=include_listed,
        include_otc=include_otc,
        include_etf=include_etf,
    )


def _merge_quotes(
    metas: list[StockMeta],
    snapshots: list[dict[str, Any]],
) -> pd.DataFrame:
    meta_index = build_meta_index(metas)
    rows: list[dict[str, Any]] = []
    for snap in snapshots:
        code = snap.get("code", "")
        meta = meta_index.get(code)
        if meta is None:
            continue
        rows.append(
            {
                "code": code,
                "name": meta.name,
                "market": meta.market,
                "industry": meta.industry,
                "kind": meta.kind,
                "category": category_of(meta),
                "label": f"{code} {meta.name}",
                "close": snap.get("close", 0.0),
                "change_price": snap.get("change_price", 0.0),
                "change_rate": snap.get("change_rate", 0.0),
                "total_amount": snap.get("total_amount", 0),
                "total_volume": snap.get("total_volume", 0),
                "volume_ratio": snap.get("volume_ratio", 0.0),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df[df["total_amount"] > 0].copy()


def _fetch_quotes(fetcher: ShioajiFetcher, metas: list[StockMeta]) -> None:
    codes = [m.code for m in metas]
    with st.spinner(f"抓取 {len(codes)} 檔行情（分批 ≤{config.SNAPSHOT_BATCH_SIZE}）..."):
        try:
            records, missing = fetcher.fetch_snapshots(codes)
            usage = fetcher.usage()
            st.session_state.quotes = records
            st.session_state.missing_codes = missing
            st.session_state.last_updated = datetime.now()
            st.session_state.usage_info = usage
            st.session_state.fetch_error = None
        except Exception as exc:  # noqa: BLE001
            st.session_state.fetch_error = str(exc)


def _render_usage(usage: UsageInfo | None) -> None:
    if usage is None:
        st.info("尚未查詢 API 流量。")
        return

    st.progress(min(max(usage.usage_ratio, 0.0), 1.0))
    st.caption(
        f"API 流量：{usage.used_mb:.2f} MB / {usage.limit_mb:.0f} MB "
        f"（剩餘 {usage.remaining_mb:.2f} MB，連線 {usage.connections}）"
    )
    if usage.remaining_bytes < config.USAGE_WARN_REMAINING_BYTES:
        st.warning(
            f"剩餘流量低於 {config.USAGE_WARN_REMAINING_BYTES // 1024 // 1024} MB，"
            "已建議停止自動刷新以避免觸及限流。"
        )


def _build_treemap(
    df: pd.DataFrame,
    size_col: str,
    color_range: float,
    title: str,
    path: list,
) -> px.Figure:
    plot_df = df.copy()
    plot_df["price_text"] = plot_df["close"].map(lambda x: f"{x:.2f}")
    plot_df["change_text"] = plot_df["change_rate"].map(lambda x: f"{x:+.2f}%")

    fig = px.treemap(
        plot_df,
        path=path,
        values=size_col,
        color="change_rate",
        color_continuous_scale=config.TREEMAP_COLORSCALE,
        range_color=[-color_range, color_range],
        color_continuous_midpoint=0,
        custom_data=["price_text", "change_text"],
        hover_data={
            "code": True,
            "close": ":.2f",
            "change_rate": ":.2f",
            "total_amount": ":,",
            "total_volume": ":,",
            "market": False,
            "industry": False,
            "name": False,
            "price_text": False,
            "change_text": False,
            "category": False,
        },
        title=title,
    )
    fig.update_layout(
        margin=dict(t=50, l=10, r=10, b=10),
        uniformtext_minsize=8,
        uniformtext_mode="hide",
        height=520,
    )
    fig.update_traces(
        texttemplate="%{label}<br>%{customdata[0]}<br>%{customdata[1]}",
        textinfo="text",
        textfont=dict(size=12),
        insidetextfont=dict(size=11),
    )
    return fig


def _render_treemap_panel(
    df: pd.DataFrame,
    panel_title: str,
    root_label: str,
    categories: tuple[str, ...],
    path_suffix: list[str],
    size_col: str,
    color_range: float,
) -> None:
    panel_df = df[df["category"].isin(categories)].copy()
    st.subheader(panel_title)
    if panel_df.empty:
        st.info("此分類尚無成交資料。")
        return

    st.caption(
        f"有成交 {len(panel_df)} 檔｜"
        f"平均漲跌幅 {panel_df['change_rate'].mean():.2f}%｜"
        f"上漲 {int((panel_df['change_rate'] > 0).sum())}｜"
        f"下跌 {int((panel_df['change_rate'] < 0).sum())}"
    )
    path = [px.Constant(root_label), *path_suffix]
    fig = _build_treemap(
        panel_df,
        size_col=size_col,
        color_range=color_range,
        title=f"{panel_title}（大小={'成交額' if size_col == 'total_amount' else '成交量'}，顏色=漲跌幅%）",
        path=path,
    )
    st.plotly_chart(fig, use_container_width=True)


def render() -> None:
    st.set_page_config(
        page_title="台股 Treemap Debug UI",
        page_icon="📊",
        layout="wide",
    )
    st.title("台股即時 Treemap")
    st.caption("資料來源：Shioaji snapshots | 防限流：分批抓取 + 滑動視窗速率限制")

    _init_session_state()

    with st.sidebar:
        st.header("控制面板")
        include_listed = st.checkbox("上市", value=True)
        include_otc = st.checkbox("上櫃", value=True)
        include_etf = st.checkbox("ETF", value=True)

        size_metric = st.radio(
            "Treemap 大小",
            options=["total_amount", "total_volume"],
            format_func=lambda x: "成交額" if x == "total_amount" else "成交量",
            index=0,
        )
        color_range = st.slider(
            "漲跌幅顏色範圍 (±%)",
            min_value=1.0,
            max_value=10.0,
            value=config.DEFAULT_COLOR_RANGE_PCT,
            step=0.5,
        )

        auto_refresh = st.checkbox("自動刷新", value=False)
        refresh_interval = st.number_input(
            "刷新間隔（秒）",
            min_value=config.MIN_AUTO_REFRESH_SEC,
            max_value=300,
            value=config.MIN_AUTO_REFRESH_SEC,
            step=5,
            disabled=not auto_refresh,
        )

        if st.button("更新行情", type="primary", use_container_width=True):
            metas = _filter_universe(include_listed, include_otc, include_etf)
            fetcher = get_fetcher()
            _fetch_quotes(fetcher, metas)

        if st.session_state.quotes:
            if st.button("匯出 .txt（上市/上櫃/ETF）", use_container_width=True):
                metas = _filter_universe(include_listed, include_otc, include_etf)
                meta_index = build_meta_index(metas)
                paths = export_snapshots(st.session_state.quotes, meta_index)
                if paths:
                    for p in paths:
                        st.success(f"已匯出：{p.name}")
                else:
                    st.warning("無可匯出的行情資料。")

        st.divider()
        st.subheader("API 流量")
        _render_usage(st.session_state.usage_info)

    usage: UsageInfo | None = st.session_state.usage_info
    low_usage = (
        usage is not None
        and usage.remaining_bytes < config.USAGE_WARN_REMAINING_BYTES
    )
    if auto_refresh and not low_usage:
        st.caption(f"自動刷新中，每 {refresh_interval} 秒更新一次")
        st.autorefresh(interval=refresh_interval * 1000, key="treemap_autorefresh")
        metas = _filter_universe(include_listed, include_otc, include_etf)
        fetcher = get_fetcher()
        _fetch_quotes(fetcher, metas)

    if st.session_state.fetch_error:
        st.error(f"抓取失敗：{st.session_state.fetch_error}")

    if st.session_state.last_updated:
        st.success(f"最後更新：{st.session_state.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")

    missing = st.session_state.missing_codes
    if missing:
        st.warning(
            f"找不到商品檔的代號（{len(missing)} 檔）：{', '.join(missing[:20])}"
            + (" ..." if len(missing) > 20 else "")
        )

    metas = _filter_universe(include_listed, include_otc, include_etf)
    df = _merge_quotes(metas, st.session_state.quotes)

    if df.empty:
        st.info("尚無行情資料。請在側欄按「更新行情」開始抓取。")
        st.metric("標的數", len(metas))
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("有成交標的", len(df))
    col2.metric("平均漲跌幅", f"{df['change_rate'].mean():.2f}%")
    col3.metric("上漲家數", int((df["change_rate"] > 0).sum()))
    col4.metric("下跌家數", int((df["change_rate"] < 0).sum()))

    st.divider()

    _render_treemap_panel(
        df,
        panel_title="1. 上市 + 上櫃股票",
        root_label="上市+上櫃",
        categories=("listed", "otc"),
        path_suffix=["market", "industry", "name"],
        size_col=size_metric,
        color_range=color_range,
    )
    _render_treemap_panel(
        df,
        panel_title="2. 上市股票",
        root_label="上市",
        categories=("listed",),
        path_suffix=["market", "industry", "name"],
        size_col=size_metric,
        color_range=color_range,
    )
    _render_treemap_panel(
        df,
        panel_title="3. 上櫃股票",
        root_label="上櫃",
        categories=("otc",),
        path_suffix=["industry", "name"],
        size_col=size_metric,
        color_range=color_range,
    )
    _render_treemap_panel(
        df,
        panel_title="4. ETF",
        root_label="ETF",
        categories=("etf",),
        path_suffix=["name"],
        size_col=size_metric,
        color_range=color_range,
    )

    with st.expander("行情表格（前 100 筆）"):
        display_df = df.sort_values("total_amount", ascending=False).head(100)
        st.dataframe(
            display_df[
                ["code", "name", "market", "industry", "close", "change_rate", "total_amount"]
            ],
            use_container_width=True,
        )
