# -*- coding: utf-8 -*-
"""OFmedia 廣告儀表板(雲端版)

資料源:OceanFishooter 廣告儀表板 Google Sheet 的 6 個 _raw 分頁
分頁：投放總覽 / 媒體對比 / 地區・OS / 媒體深度
"""
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import theme
import grid
from theme import MEDIA_COLORS
from auth import require_password
from data import (load_unified, load_meta_raw, load_asa_raw,
                  load_google_raw)
from calendar_view import render as render_calendar_todo
import calendar_store
import html

st.set_page_config(
    page_title="Ocean Fishooter 廣告儀表板",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(theme.inject_css(), unsafe_allow_html=True)

require_password()

# ──────────────────────────────────────────────────────────────────────
#  通用 KPI 卡片元件
# ──────────────────────────────────────────────────────────────────────
def _kpi_pack(df: pd.DataFrame) -> dict:
    spend = df["spend"].sum()
    imp = df["impressions"].sum()
    clicks = df["clicks"].sum()
    installs = df["installs"].sum()
    return {
        "spend": spend, "imp": imp, "clicks": clicks, "installs": installs,
        "ctr": clicks / imp * 100 if imp > 0 else 0,
        "cpc": spend / clicks if clicks > 0 else 0,
        "cpm": spend / imp * 1000 if imp > 0 else 0,
        "cpi": spend / installs if installs > 0 else 0,
        "cvr": installs / clicks * 100 if clicks > 0 else 0,
    }


def _compute_sparks(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    max_d = df["date"].max()
    min_d = max_d - pd.Timedelta(days=6)
    df7 = df[df["date"] >= min_d]
    if df7.empty:
        return {}
    d = df7.groupby("date").agg(
        spend=("spend", "sum"),
        imp=("impressions", "sum"),
        clicks=("clicks", "sum"),
        installs=("installs", "sum"),
    ).sort_index()
    d["ctr"] = (d["clicks"] / d["imp"] * 100).fillna(0)
    d["cpc"] = (d["spend"] / d["clicks"]).replace([float("inf"), float("-inf")], 0).fillna(0)
    d["cpm"] = (d["spend"] / d["imp"] * 1000).replace([float("inf"), float("-inf")], 0).fillna(0)
    d["cpi"] = (d["spend"] / d["installs"]).replace([float("inf"), float("-inf")], 0).fillna(0)
    d["cvr"] = (d["installs"] / d["clicks"] * 100).fillna(0)
    return {k: d[k].tolist() for k in
            ["spend", "imp", "clicks", "installs", "ctr", "cpc", "cpm", "cpi", "cvr"]
            if k in d.columns}


def show_kpis(df: pd.DataFrame, df_prev: pd.DataFrame = None) -> None:
    """八個 KPI：規模四個（藍）＋ 效率四個（黃），與對比期比較。"""
    curr = _kpi_pack(df)
    prev = _kpi_pack(df_prev) if df_prev is not None and not df_prev.empty else None
    sparks = _compute_sparks(df)

    def delta(key):
        """與對比期的變化百分比；沒有對比期或上期為 0 時回 None。"""
        if not prev or not prev.get(key):
            return None
        return (curr[key] - prev[key]) / prev[key] * 100

    cpi_txt = f"${curr['cpi']:.2f}" if curr["cpi"] > 0 else "—"
    # 每項：標籤、顯示值、完整值（hover 用）、sparkline 的 key、是否越大越糟
    groups = [
        ("規模", "花費與量體", "vol", [
            ("花費", f"${theme.fmt_compact(curr['spend'])}",
             f"${curr['spend']:,.2f}", "spend", False),
            ("曝光", theme.fmt_compact(curr["imp"]),
             f"{curr['imp']:,.0f}", "imp", False),
            ("點擊", theme.fmt_compact(curr["clicks"]),
             f"{curr['clicks']:,.0f}", "clicks", False),
            ("安裝", theme.fmt_compact(curr["installs"]),
             f"{curr['installs']:,.0f}", "installs", False),
        ]),
        ("效率", "右側迷你線為近 7 天走勢", "rate", [
            ("CPM", f"${curr['cpm']:.2f}", "", "cpm", True),
            ("CTR", f"{curr['ctr']:.2f}%", "", "ctr", False),
            ("CVR", f"{curr['cvr']:.2f}%", "", "cvr", False),
            ("CPI", cpi_txt, "", "cpi", True),
        ]),
    ]
    for title, desc, cat, items in groups:
        st.markdown(theme.section(title, desc), unsafe_allow_html=True)
        for col, (label, value, full, key, inverse) in zip(st.columns(4), items):
            col.markdown(
                theme.kpi_card(label, value, delta(key), cat, inverse,
                               sparks.get(key, []), full),
                unsafe_allow_html=True,
            )


# ──────────────────────────────────────────────────────────────────────
#  圖表
# ──────────────────────────────────────────────────────────────────────
def show_daily_trend(df: pd.DataFrame, ops: list = None) -> None:
    """花費（柱）＋ 安裝與 CPI（線）三軸圖，頂端三角標記當天的廣告操作。"""
    daily = df.groupby("date").agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
    ).reset_index()
    daily["cpi"] = (daily["spend"] / daily["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["date"], y=daily["spend"], name="花費",
        marker_color=theme.ACCENT, opacity=0.40, yaxis="y1",
        hovertemplate="花費 $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["installs"], name="安裝",
        mode="lines+markers", line=dict(color=theme.POS, width=2.2),
        marker=dict(size=5), yaxis="y2",
        hovertemplate="安裝 %{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["cpi"], name="CPI",
        mode="lines+markers", line=dict(color=theme.WARN, width=2.2, dash="dot"),
        marker=dict(size=5), yaxis="y3",
        hovertemplate="CPI $%{y:.2f}<extra></extra>",
    ))

    # 操作標記：同一天多筆合併成一個三角，hover 展開內容
    if ops and not daily.empty:
        from collections import defaultdict
        by_date = defaultdict(list)
        for o in ops:
            if o.get("date"):
                by_date[o["date"]].append(o)
        mk_x, mk_hover = [], []
        for d in sorted(by_date):
            segs = []
            for o in by_date[d]:
                seg = o.get("op_type", "")
                if o.get("media"):
                    seg += f"·{o['media']}"
                if o.get("campaign"):
                    seg += f"·{o['campaign']}"
                if o.get("note"):
                    seg += f"（{o['note']}）"
                segs.append(seg)
            mk_x.append(pd.to_datetime(d))
            mk_hover.append("<br>".join(segs))
        top = float(daily["spend"].max()) * 1.08
        fig.add_trace(go.Scatter(
            x=mk_x, y=[top] * len(mk_x), mode="markers", name="操作",
            marker=dict(symbol="triangle-up", size=11, color=theme.WARN,
                        line=dict(color=theme.BG, width=1)),
            yaxis="y1", hovertext=mk_hover,
            hovertemplate="%{hovertext}<extra></extra>",
        ))

    theme.style_fig(fig, height=theme.H_MAIN,
                    margin=dict(t=34, b=22, l=10, r=78))
    fig.update_layout(
        hovermode="x unified",
        xaxis=dict(domain=[0, 0.93], tickformat="%m/%d", showgrid=False),
        yaxis=dict(title=dict(text="花費 ($)", font=dict(color=theme.ACCENT_HI, size=11)),
                   showgrid=True, gridcolor=theme.BORDER,
                   tickfont=dict(color=theme.ACCENT_HI)),
        yaxis2=dict(title=dict(text="安裝", font=dict(color=theme.POS, size=11)),
                    overlaying="y", side="right", showgrid=False,
                    position=0.93, tickfont=dict(color=theme.POS)),
        yaxis3=dict(title=dict(text="CPI ($)", font=dict(color=theme.WARN, size=11)),
                    overlaying="y", side="right", showgrid=False,
                    anchor="free", position=1.0, tickfont=dict(color=theme.WARN)),
    )
    st.plotly_chart(fig, width='stretch', config=theme.PLOTLY_CONFIG)


def get_filtered_ops(date_range, media_choice: str = "全部") -> list:
    """取該期間＋媒體篩選下的廣告操作（日期新到舊）。供趨勢圖標記與清單共用。"""
    try:
        ops = calendar_store.list_ops()
    except Exception:
        return []
    if len(date_range) == 2:
        s, e = date_range[0].isoformat(), date_range[1].isoformat()
    else:
        s, e = "0000-00-00", "9999-99-99"
    rows = [o for o in ops
            if s <= (o.get("date", "") or "") <= e
            and (media_choice == "全部" or o.get("media") == media_choice)]
    rows.sort(key=lambda o: (o.get("date", ""), o.get("id", "")), reverse=True)
    return rows


def show_ops_log(ops: list) -> None:
    """條列期間內的廣告操作，與上方趨勢圖的三角標記對照。"""
    if not ops:
        st.caption("此期間／篩選下沒有廣告操作紀錄。")
        return

    def clip(s, n):
        s = s or ""
        return (s[:n] + "…") if len(s) > n else s

    rows = []
    for o in ops:
        op = html.escape(o.get("op_type", ""))
        med = html.escape(o.get("media", ""))
        camp = html.escape(clip(o.get("campaign", ""), 26))
        note = html.escape(clip(o.get("note", ""), 52))  # 完整備註看「行事曆・待辦」
        mid = "　·　".join([p for p in (med, camp) if p])
        note_html = f'<span class="of-op-note">{note}</span>' if note else ""
        rows.append(
            f'<div class="of-op">'
            f'<span class="of-op-date">{o.get("date", "")}</span>'
            f'<span class="of-op-type">{op}</span>'
            f'<span>{mid}</span>{note_html}</div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def show_media_mix(df: pd.DataFrame) -> None:
    """花費與安裝的媒體占比：兩個甜甜圈，中心放總計。"""
    stats = df.groupby("media").agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
    ).reset_index().sort_values("spend", ascending=False)
    if stats.empty:
        st.caption("此條件下無資料。")
        return

    colors = [MEDIA_COLORS.get(m, theme.ACCENT) for m in stats["media"]]
    specs = [
        ("spend", "花費", f"${stats['spend'].sum():,.0f}", "$%{value:,.0f}"),
        ("installs", "安裝", f"{stats['installs'].sum():,.0f}", "%{value:,.0f}"),
    ]
    for col, (value_col, label, total, val_fmt) in zip(st.columns(2), specs):
        fig = go.Figure(go.Pie(
            labels=stats["media"], values=stats[value_col], hole=0.64, sort=False,
            marker=dict(colors=colors, line=dict(color=theme.BG, width=2)),
            textinfo="none",
            hovertemplate="%{label}　" + val_fmt + "　(%{percent})<extra></extra>",
        ))
        theme.style_fig(fig, height=theme.H_SUB, margin=dict(t=10, b=30, l=10, r=10))
        fig.update_layout(
            legend=dict(orientation="h", yanchor="top", y=0, xanchor="center", x=0.5),
            annotations=[dict(
                text=f'<span style="font-size:11px;color:{theme.TEXT_DIM}">{label}</span>'
                     f'<br><span style="font-size:17px;font-weight:700;'
                     f'color:{theme.TEXT}">{total}</span>',
                showarrow=False, x=0.5, y=0.5, xanchor="center", yanchor="middle",
            )],
        )
        col.plotly_chart(fig, width='stretch', config=theme.PLOTLY_CONFIG)


def show_alerts(df: pd.DataFrame, df_prev: pd.DataFrame = None) -> None:
    """與對比期比較後的異常清單。level：neg 惡化 / pos 改善 / warn 注意。"""
    alerts = []
    if df_prev is not None and not df_prev.empty:
        # 媒體 CPI 變化
        c = df.groupby("media").agg(spend=("spend", "sum"),
                                    installs=("installs", "sum")).reset_index()
        c["cpi"] = (c["spend"] / c["installs"]).replace(
            [float("inf"), float("-inf")], 0).fillna(0)
        p = df_prev.groupby("media").agg(spend=("spend", "sum"),
                                         installs=("installs", "sum")).reset_index()
        p["cpi"] = (p["spend"] / p["installs"]).replace(
            [float("inf"), float("-inf")], 0).fillna(0)
        merged = c.merge(p[["media", "cpi"]], on="media", suffixes=("", "_prev"))
        for _, r in merged.iterrows():
            if r["cpi_prev"] > 0 and r["cpi"] > 0:
                chg = (r["cpi"] - r["cpi_prev"]) / r["cpi_prev"] * 100
                media_name = html.escape(str(r["media"]))
                if chg > 30:
                    alerts.append(("neg", "CPI 上升",
                                   f"<b>{media_name}</b> CPI ${r['cpi_prev']:.2f} → "
                                   f"${r['cpi']:.2f}（{chg:+.0f}%），檢查素材或受眾"))
                elif chg < -25 and r["installs"] > 50:
                    alerts.append(("pos", "CPI 改善",
                                   f"<b>{media_name}</b> CPI ${r['cpi_prev']:.2f} → "
                                   f"${r['cpi']:.2f}（{chg:+.0f}%），可考慮加碼"))
        # 安裝量驟降
        cv = df.groupby("media")["installs"].sum()
        pv = df_prev.groupby("media")["installs"].sum()
        for media in cv.index:
            if media in pv.index and pv[media] > 50:
                chg = (cv[media] - pv[media]) / pv[media] * 100
                if chg < -40:
                    alerts.append(("neg", "安裝驟降",
                                   f"<b>{html.escape(str(media))}</b> 安裝 "
                                   f"{pv[media]:,.0f} → {cv[media]:,.0f}"
                                   f"（{chg:+.0f}%）"))

    # 預算過度集中（不需要對比期）
    media_spend = df.groupby("media")["spend"].sum().reset_index()
    total = media_spend["spend"].sum()
    for _, r in media_spend.iterrows():
        pct = r["spend"] / total * 100 if total > 0 else 0
        if pct > 60:
            alerts.append(("warn", "預算集中",
                           f"<b>{html.escape(str(r['media']))}</b> 佔總花費 {pct:.1f}%，"
                           f"單一媒體依賴風險高"))

    if not alerts:
        st.caption("目前無重大警示。")
        return
    # 惡化的排前面，改善的放最後
    order = {"neg": 0, "warn": 1, "pos": 2}
    alerts.sort(key=lambda a: order[a[0]])
    st.markdown("".join(theme.alert(lv, tag, msg) for lv, tag, msg in alerts),
                unsafe_allow_html=True)


def show_media_compare(df: pd.DataFrame) -> None:
    """六媒體並排對比表 ＋ CPI 排行。表格欄位保留數值型別，可正確排序。"""
    stats = df.groupby("media").agg(
        spend=("spend", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        installs=("installs", "sum"),
    ).reset_index()
    if stats.empty:
        st.caption("此條件下無資料。")
        return
    stats["ctr"] = (stats["clicks"] / stats["impressions"] * 100).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    stats["cpc"] = (stats["spend"] / stats["clicks"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    stats["cpi"] = (stats["spend"] / stats["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    total_spend = stats["spend"].sum()
    stats["share"] = (stats["spend"] / total_spend * 100).round(1) if total_spend > 0 else 0
    stats = stats.sort_values("spend", ascending=False)

    grid.data_grid(
        stats[["media", "spend", "share", "installs", "cpi", "ctr", "cpc"]],
        [
            grid.col("media", "媒體", width=120, pinned="left"),
            grid.col("spend", "花費 ($)", "money", width=120),
            grid.col("share", "花費占比", "bar", flex=1,
                     help="占期間總花費的比例"),
            grid.col("installs", "安裝", "int", width=100),
            grid.col("cpi", "CPI", "cost", width=96, help="花費 / 安裝"),
            grid.col("ctr", "CTR", "pct", width=92, help="點擊 / 曝光"),
            grid.col("cpc", "CPC", "cost", width=96, help="花費 / 點擊"),
        ],
        key="grid_media_compare", selection="none")

    # CPI 排行：安裝量太少的媒體 CPI 是雜訊，門檻設 10
    rank = stats[stats["installs"] >= 10].sort_values("cpi")
    if rank.empty:
        return
    st.markdown(theme.section("CPI 排行", "最便宜與最貴各自標色；安裝數滿 10 才列入"),
                unsafe_allow_html=True)
    # 六個媒體各給一色會變成一排彩條，反而看不出重點；這裡只標出最便宜
    # 與最貴的兩端，其餘用中性色。
    bar_colors = [theme.BORDER_HI] * len(rank)
    if len(rank) >= 2:
        bar_colors[0] = theme.POS
        bar_colors[-1] = theme.NEG
    fig = go.Figure(go.Bar(
        x=rank["cpi"], y=rank["media"], orientation="h",
        marker=dict(color=bar_colors),
        text=[f"${v:.2f}" for v in rank["cpi"]],
        textposition="outside", textfont=dict(color=theme.TEXT_MID, size=11),
        hovertemplate="%{y}　CPI $%{x:.2f}<extra></extra>",
    ))
    theme.style_fig(fig, height=max(theme.H_MINI, 34 * len(rank) + 36),
                    legend=False, margin=dict(t=10, b=20, l=10, r=44))
    fig.update_layout(bargap=0.45,
                      xaxis=dict(showgrid=True, gridcolor=theme.BORDER,
                                 showticklabels=False),
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width='stretch', config=theme.PLOTLY_CONFIG)


def show_geo_os(df: pd.DataFrame) -> None:
    """iOS 與 Android 對照、國家排行、國家 × 媒體 CPI 熱力圖。"""
    st.markdown(theme.section("iOS 與 Android"), unsafe_allow_html=True)
    df_ios = df[df["os"].str.upper().isin(["IOS"])]
    df_and = df[df["os"].str.upper().isin(["AND", "ANDROID"])]
    c1, c2 = st.columns(2)
    for col, sub, label in [(c1, df_ios, "iOS"), (c2, df_and, "Android")]:
        k = _kpi_pack(sub)
        cpi = f"${k['cpi']:.2f}" if k["cpi"] > 0 else "—"
        rows = [("花費", f"${k['spend']:,.0f}"), ("安裝", f"{k['installs']:,.0f}"),
                ("CPI", cpi), ("CTR", f"{k['ctr']:.2f}%"), ("CVR", f"{k['cvr']:.2f}%")]
        body = "".join(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:4px 0;border-bottom:1px solid {theme.BORDER}">'
            f'<span style="color:{theme.TEXT_MID};font-size:12px">{n}</span>'
            f'<span style="color:{theme.TEXT};font-weight:600;font-size:13px">{v}</span>'
            f'</div>' for n, v in rows)
        col.markdown(
            f'<div style="background:{theme.SURFACE};border:1px solid {theme.BORDER};'
            f'border-radius:{theme.R_MD};padding:12px 14px">'
            f'<div style="font-size:13px;font-weight:700;color:{theme.TEXT};'
            f'margin-bottom:6px">{label}</div>{body}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(theme.section("國家表現", "前 15 名，依花費排序"),
                unsafe_allow_html=True)
    geo = df.groupby("country").agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
        clicks=("clicks", "sum"),
    ).reset_index()
    geo["cpi"] = (geo["spend"] / geo["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    geo["cpc"] = (geo["spend"] / geo["clicks"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    top15 = geo.sort_values("spend", ascending=False).head(15)
    grid.data_grid(
        top15[["country", "spend", "installs", "cpi", "cpc"]],
        [
            grid.col("country", "國家", width=120, pinned="left"),
            grid.col("spend", "花費 ($)", "money", flex=1),
            grid.col("installs", "安裝", "int", flex=1),
            grid.col("cpi", "CPI", "cost", flex=1),
            grid.col("cpc", "CPC", "cost", flex=1),
        ],
        key="grid_geo_country", selection="none")

    st.markdown(theme.section("國家 × 媒體 CPI", "綠＝便宜，紅＝貴；空格代表無安裝"),
                unsafe_allow_html=True)
    heat = df[df["country"].isin(top15["country"].tolist())]
    pivot = heat.pivot_table(index="country", columns="media",
                             values=["spend", "installs"], aggfunc="sum",
                             fill_value=0)
    if pivot.empty:
        st.caption("此條件下無資料。")
        return
    cpi_mat = (pivot["spend"] / pivot["installs"].replace(0, float("nan"))).round(2)
    fig = px.imshow(cpi_mat, color_continuous_scale="RdYlGn_r",
                    labels=dict(color="CPI ($)"), aspect="auto", text_auto=".2f")
    theme.style_fig(fig, height=400, legend=False,
                    margin=dict(t=10, b=10, l=10, r=10))
    fig.update_layout(coloraxis_colorbar=dict(
        thickness=10, len=0.7, outlinewidth=0,
        tickfont=dict(color=theme.TEXT_MID, size=10),
        title=dict(font=dict(color=theme.TEXT_MID, size=10))))
    fig.update_xaxes(side="top", title=None)
    fig.update_yaxes(title=None)
    st.plotly_chart(fig, width='stretch', config=theme.PLOTLY_CONFIG)


def show_campaign_table(df: pd.DataFrame, media_filter: str = "全部",
                        key: str = "grid_campaign") -> tuple:
    """單一媒體的 Campaign 排行。

    與 Meta 深度頁共用同一套指標、快篩與欄位，操作方式也一致：點一列看
    走勢、Ctrl 複選做對比。回傳 (該媒體的原始資料, 被選取的 campaign)。
    """
    sub = df if media_filter == "全部" else df[df["media"] == media_filter]
    if sub.empty:
        st.info("此條件下無資料")
        return sub, []

    stats = _add_cpi_trend_cols(_meta_metrics(sub, "campaign"), sub, "campaign")
    mode = st.segmented_control("快篩", QUICK_MODES, default="全部",
                                key=f"qf_{key}") or "全部"
    view = _quick_filter(stats, mode)
    if view.empty:
        st.info(f"「{mode}」條件下沒有 Campaign。")
        return sub, []
    if mode != "全部":
        st.caption(f"{mode}：{len(view)} / {len(stats)} 個 Campaign")

    sel = grid.data_grid(view, _level_columns("campaign", "Campaign", False),
                         key=key, selection="multi")
    return sub, grid.selected_values(sel, "campaign")


# ──────────────────────────────────────────────────────────────────────
#  深度頁籤
# ──────────────────────────────────────────────────────────────────────
_STATUS_DISPLAY = {
    # 投放中
    "active": "🟢 投放中",
    "delivering": "🟢 投放中",
    "enabled": "🟢 投放中",
    # 暫停 / 未啟用(不加 emoji,視覺乾淨)
    "paused": "暫停",
    "inactive": "暫停",
    "not_delivering": "暫停",
    "campaign_paused": "Campaign 暫停",
    "adset_paused": "Ad Set 暫停",
    # 已歸檔 / 刪除
    "archived": "已封存",
    "deleted": "已刪除",
    "removed": "已刪除",
    # 審查中
    "in_review": "審查中",
    "pending_review": "審查中",
    "learning": "📚 學習中",
    # 未通過
    "disapproved": "❌ 未通過",
    "rejected": "❌ 未通過",
}


def _status_zh(s: str) -> str:
    if not s or pd.isna(s):
        return "—"
    return _STATUS_DISPLAY.get(str(s).strip().lower(), str(s))


def _latest_status_map(df: pd.DataFrame, group_col: str) -> dict:
    """取每組(如每個 ad)在期間內最新日期的 status,回傳 dict。"""
    if df.empty or "status" not in df.columns:
        return {}
    sub = df[df["status"].notna() & (df["status"].astype(str).str.strip() != "")]
    if sub.empty:
        return {}
    latest = sub.sort_values("date").groupby(group_col).tail(1)
    return dict(zip(latest[group_col], latest["status"]))


def _meta_ad_detail_chart(sub: pd.DataFrame, name: str,
                          start_date, end_date, group_col: str = "ad") -> None:
    """某個項目（素材 / Campaign / Ad Group）的 14 天走勢。

    上：花費、安裝、CPI 三軸主圖
    下：CTR + CVR 漏斗、CPM 流量成本（X 軸與主圖對齊，可垂直比對同一天）
    group_col 決定聚合層級（ad / campaign / ad_group）。
    """
    ad_df = sub[sub[group_col] == name].copy()
    ad_df["date_only"] = ad_df["date"].dt.normalize()
    daily = ad_df.groupby("date_only").agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
    ).reset_index()

    # 補齊沒有數據的日期，折線才不會把中斷的兩天連成一直線
    full = pd.DataFrame({"date_only": pd.date_range(
        start=start_date, end=end_date.normalize(), freq="D")})
    full = full.merge(daily, on="date_only", how="left").fillna(0)
    full["cpi"] = full.apply(
        lambda r: round(r["spend"] / r["installs"], 2) if r["installs"] > 0 else 0,
        axis=1)
    full["ctr"] = full.apply(
        lambda r: round(r["clicks"] / r["impressions"] * 100, 2) if r["impressions"] > 0 else 0,
        axis=1)
    full["cvr"] = full.apply(
        lambda r: round(r["installs"] / r["clicks"] * 100, 2) if r["clicks"] > 0 else 0,
        axis=1)
    full["cpm"] = full.apply(
        lambda r: round(r["spend"] / r["impressions"] * 1000, 2) if r["impressions"] > 0 else 0,
        axis=1)

    with st.expander("怎麼看這張圖（CPI / 花費 / 安裝）", expanded=False):
        st.markdown("""
| 看到的型態 | 判讀 |
|---|---|
| CPI↑、花費平、**安裝↓** | 量在掉，效率惡化 |
| CPI↑、**花費↑**、安裝沒等比漲 | 加碼踩到天花板 |
| CPI↑、花費↑、安裝↑ | 正常擴量，成本微升可接受 |
| **CPI↓、安裝↑** | 黃金狀態，值得加碼 |
| 某天 CPI 暴衝、花費很低 | 量太少的雜訊，別當真 |
""")

    x_start = start_date - pd.Timedelta(hours=12)
    x_end = end_date.normalize() + pd.Timedelta(hours=12)
    x_axis = dict(domain=[0, 0.93], tickformat="%m/%d", type="date",
                  range=[x_start, x_end], showgrid=False)

    # 主圖：花費（柱）、安裝（綠線）、CPI（黃線，與 KPI 的效率色一致）
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=full["date_only"], y=full["spend"], name="花費",
        marker_color=theme.ACCENT, opacity=0.30, yaxis="y1",
        hovertemplate="花費 $%{y:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=full["date_only"], y=full["installs"], name="安裝",
        mode="lines+markers", line=dict(color=theme.POS, width=2),
        marker=dict(size=5), yaxis="y2",
        hovertemplate="安裝 %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=full["date_only"], y=full["cpi"], name="CPI",
        mode="lines+markers", line=dict(color=theme.WARN, width=2.4),
        marker=dict(size=6), yaxis="y3",
        hovertemplate="CPI $%{y:.2f}<extra></extra>"))
    theme.style_fig(fig, height=300, margin=dict(t=34, b=20, l=54, r=78))
    fig.update_layout(
        hovermode="x unified", xaxis=x_axis,
        yaxis=dict(title=dict(text="花費 ($)", font=dict(color=theme.ACCENT_HI, size=11)),
                   showgrid=True, gridcolor=theme.BORDER, automargin=False,
                   tickfont=dict(color=theme.ACCENT_HI)),
        yaxis2=dict(title=dict(text="安裝", font=dict(color=theme.POS, size=11)),
                    overlaying="y", side="right", showgrid=False,
                    position=0.93, tickfont=dict(color=theme.POS)),
        yaxis3=dict(title=dict(text="CPI ($)", font=dict(color=theme.WARN, size=11)),
                    overlaying="y", side="right", showgrid=False,
                    anchor="free", position=1.0, tickfont=dict(color=theme.WARN)),
    )
    st.plotly_chart(fig, width='stretch', config=theme.PLOTLY_CONFIG)

    with st.expander("怎麼看 CTR / CVR（漏斗診斷）", expanded=False):
        st.markdown("""
| 看到的型態 | 判讀 |
|---|---|
| **CTR↓、CVR 穩** | 素材吸不到人，該換創意 |
| **CTR 穩、CVR↓** | 吸到人但不裝，落地頁或受眾精準度問題 |
| **兩個都↓** | 整體素材疲乏或受眾飽和 |

> 漏斗順序：曝光 ─CTR→ 點擊 ─CVR→ 安裝
""")

    # 漏斗：CTR（素材吸引力）與 CVR（點擊後轉化）
    C_CTR, C_CVR = theme.CTR_C, theme.CVR_C
    funnel = go.Figure()
    funnel.add_trace(go.Scatter(
        x=full["date_only"], y=full["ctr"], name="CTR",
        mode="lines+markers", line=dict(color=C_CTR, width=2),
        marker=dict(size=4), yaxis="y1",
        hovertemplate="CTR %{y:.2f}%<extra></extra>"))
    funnel.add_trace(go.Scatter(
        x=full["date_only"], y=full["cvr"], name="CVR",
        mode="lines+markers", line=dict(color=C_CVR, width=2),
        marker=dict(size=4), yaxis="y2",
        hovertemplate="CVR %{y:.2f}%<extra></extra>"))
    theme.style_fig(funnel, height=theme.H_SUB, margin=dict(t=32, b=18, l=54, r=78),
                    title="CTR 素材吸引力　CVR 點擊後轉化")
    funnel.update_layout(
        hovermode="x unified", xaxis=x_axis,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=0.93),
        yaxis=dict(title=dict(text="CTR (%)", font=dict(color=C_CTR, size=11)),
                   showgrid=True, gridcolor=theme.BORDER, rangemode="tozero",
                   automargin=False, tickfont=dict(color=C_CTR)),
        yaxis2=dict(title=dict(text="CVR (%)", font=dict(color=C_CVR, size=11)),
                    overlaying="y", side="right", showgrid=False,
                    rangemode="tozero", tickfont=dict(color=C_CVR)),
    )
    st.plotly_chart(funnel, width='stretch', config=theme.PLOTLY_CONFIG)

    # CPM：流量成本與競爭強度
    cpm_fig = go.Figure(go.Scatter(
        x=full["date_only"], y=full["cpm"], mode="lines+markers",
        line=dict(color=theme.CPM_C, width=2), marker=dict(size=4),
        hovertemplate="CPM $%{y:.2f}<extra></extra>"))
    theme.style_fig(cpm_fig, height=theme.H_MINI, legend=False,
                    margin=dict(t=30, b=18, l=54, r=78),
                    title="CPM ($)　往上漲代表流量變貴或競爭加劇",
                    title_color=theme.CPM_C)
    cpm_fig.update_layout(
        hovermode="x unified", xaxis=x_axis,
        yaxis=dict(showgrid=True, gridcolor=theme.BORDER,
                   rangemode="tozero", automargin=False))
    st.plotly_chart(cpm_fig, width='stretch', config=theme.PLOTLY_CONFIG)


def _add_cpi_trend_cols(stats: pd.DataFrame, raw_sub: pd.DataFrame,
                        group_col: str) -> pd.DataFrame:
    """加上 14 天 CPI 走勢（給 sparkline）與昨日 / 3 日 / 7 日 CPI 四欄。

    沒安裝那天的單日 CPI 記為 0；3 日與 7 日 CPI 用累積花費除以累積安裝，
    不是把每日 CPI 平均（那會被低量的日子拉歪）。
    """
    if raw_sub.empty or stats.empty:
        return stats
    max_d = raw_sub["date"].max()
    max_d_norm = max_d.normalize()
    start_14d = (max_d - pd.Timedelta(days=13)).normalize()
    sub_14d = raw_sub[raw_sub["date"] >= start_14d].copy()
    sub_14d["date_only"] = sub_14d["date"].dt.normalize()
    date_range_14d = pd.date_range(start=start_14d, end=max_d_norm, freq="D")

    daily = sub_14d.groupby([group_col, "date_only"]).agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
    ).reset_index()

    spark_map, yday_map, d3_map, d7_map = {}, {}, {}, {}
    for key in stats[group_col].unique():
        item = daily[daily[group_col] == key].set_index("date_only")
        values = []
        for d in date_range_14d:
            if d in item.index:
                sp, inst = item.loc[d, "spend"], item.loc[d, "installs"]
                values.append(round(sp / inst, 2) if inst > 0 else 0.0)
            else:
                values.append(0.0)
        spark_map[key] = values

        if max_d_norm in item.index:
            sp, inst = item.loc[max_d_norm, "spend"], item.loc[max_d_norm, "installs"]
            yday_map[key] = round(sp / inst, 2) if inst > 0 else 0.0
        else:
            yday_map[key] = 0.0

        d3 = item.loc[item.index >= max_d_norm - pd.Timedelta(days=2)]
        d3_map[key] = round(d3["spend"].sum() / d3["installs"].sum(), 2) \
            if d3["installs"].sum() > 0 else 0.0
        d7 = item.loc[item.index >= max_d_norm - pd.Timedelta(days=6)]
        d7_map[key] = round(d7["spend"].sum() / d7["installs"].sum(), 2) \
            if d7["installs"].sum() > 0 else 0.0

    stats = stats.copy()
    stats["spark"] = stats[group_col].map(spark_map)
    stats["cpi_yday"] = stats[group_col].map(yday_map)
    stats["cpi_3d"] = stats[group_col].map(d3_map)
    stats["cpi_7d"] = stats[group_col].map(d7_map)
    return stats


def _meta_metrics(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """各層級的標準指標（花費 / 安裝 / CPI / CTR / CVR / CPM），依花費排序。"""
    g = df.groupby(group_col).agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
    ).reset_index()
    g["cpi"] = (g["spend"] / g["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    g["ctr"] = (g["clicks"] / g["impressions"] * 100).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    g["cvr"] = (g["installs"] / g["clicks"] * 100).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    g["cpm"] = (g["spend"] / g["impressions"] * 1000).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    g["spend"] = g["spend"].round(0)
    return g.sort_values("spend", ascending=False)


# ── 快篩：直接對應「找該關的」與「檢查昨天異常」兩個任務 ────────────
QUICK_MODES = ["全部", "需要注意", "表現好"]


def _quick_filter(stats: pd.DataFrame, mode: str) -> pd.DataFrame:
    """依快篩模式挑出項目。需要 cpi_yday / cpi_7d 欄，沒有就原樣回傳。"""
    if mode == "全部" or stats.empty or "cpi_7d" not in stats.columns:
        return stats
    if mode == "需要注意":
        # 昨天的 CPI 比 7 日水準貴三成以上，或花了錢卻幾乎沒帶量
        worse = (stats["cpi_7d"] > 0) & (stats["cpi_yday"] > stats["cpi_7d"] * 1.3)
        wasted = (stats["spend"] > 100) & (stats["installs"] < 5)
        return stats[worse | wasted]
    # 表現好：昨天明顯比 7 日水準便宜，且量體不是零星幾個
    better = ((stats["cpi_yday"] > 0)
              & (stats["cpi_yday"] < stats["cpi_7d"] * 0.8)
              & (stats["installs"] >= 10))
    return stats[better]


def _level_columns(group_col: str, label: str, has_status: bool) -> list:
    """下鑽表格的欄位順序：診斷 CPI 要並排看，所以昨日 / 7 日 / 走勢緊跟 CPI。"""
    cols = []
    if has_status:
        cols.append(grid.col("status_zh", "狀態", width=96))
    cols += [
        grid.col(group_col, label, flex=2, pinned="left"),
        grid.col("spend", "花費 ($)", "money", width=110),
        grid.col("installs", "安裝", "int", width=90),
        grid.col("cpi", "CPI", "cost", width=92, help="期間內：花費 / 安裝"),
        grid.col("cpi_yday", "昨日", "cost", width=88, help="最新一天的 CPI"),
        grid.col("cpi_7d", "7 日", "cost", width=88,
                 help="最近 7 天累積花費 / 累積安裝"),
        grid.col("spark", "14 天走勢", "spark", width=100),
        grid.col("ctr", "CTR", "pct", width=84),
        grid.col("cvr", "CVR", "pct", width=84),
        grid.col("cpm", "CPM", "cost", width=90),
    ]
    return cols


def _selection_charts(sub: pd.DataFrame, group_col: str, names: list) -> None:
    """選一個就畫完整走勢，選多個就畫 CPI 疊圖對比。"""
    if not names:
        st.caption("點表格裡的任一列查看走勢；按住 Ctrl 或 Shift 可複選多列做對比。")
        return
    max_d = sub["date"].max()
    start_14d = (max_d - pd.Timedelta(days=13)).normalize()
    if len(names) == 1:
        st.markdown(theme.section(html.escape(str(names[0])), "14 天詳細走勢"),
                    unsafe_allow_html=True)
        _meta_ad_detail_chart(sub, names[0], start_14d, max_d, group_col=group_col)
        return

    shown = names[:5]
    extra = f"（選了 {len(names)} 個，只畫前 5 個）" if len(names) > 5 else ""
    st.markdown(theme.section("CPI 對比", f"最近 14 天{extra}"),
                unsafe_allow_html=True)
    fig = go.Figure()
    for i, name in enumerate(shown):
        item = sub[sub[group_col] == name].copy()
        item["date_only"] = item["date"].dt.normalize()
        daily = item.groupby("date_only").agg(
            spend=("spend", "sum"), installs=("installs", "sum")).reset_index()
        full = pd.DataFrame({"date_only": pd.date_range(start_14d,
                                                        max_d.normalize(), freq="D")})
        full = full.merge(daily, on="date_only", how="left").fillna(0)
        full["cpi"] = full.apply(
            lambda r: round(r["spend"] / r["installs"], 2) if r["installs"] > 0 else None,
            axis=1)
        fig.add_trace(go.Scatter(
            x=full["date_only"], y=full["cpi"], name=str(name)[:28],
            mode="lines+markers", connectgaps=True,
            line=dict(color=theme.CHART_SEQ[i % len(theme.CHART_SEQ)], width=2),
            marker=dict(size=4),
            hovertemplate=f"{str(name)[:28]}　$%{{y:.2f}}<extra></extra>"))
    theme.style_fig(fig, height=theme.H_SUB + 40,
                    margin=dict(t=34, b=22, l=54, r=16))
    fig.update_layout(hovermode="x unified",
                      xaxis=dict(tickformat="%m/%d", showgrid=False),
                      yaxis=dict(title=dict(text="CPI ($)", font=dict(size=11)),
                                 showgrid=True, gridcolor=theme.BORDER,
                                 rangemode="tozero"))
    st.plotly_chart(fig, width='stretch', config=theme.PLOTLY_CONFIG)
    st.caption("沒有安裝的日子會斷點；線段中斷代表那天沒帶到量。")


def _apply_raw_filters(df: pd.DataFrame, os_choice: str, country_choice: str) -> pd.DataFrame:
    """套用 sidebar 的 OS / 國家篩選到 raw DataFrame。"""
    if df.empty:
        return df
    if os_choice != "全部" and "os" in df.columns:
        def _norm(s):
            s = str(s).strip().upper()
            if s in ("IOS", "I"):
                return "iOS"
            if s in ("AND", "ANDROID"):
                return "Android"
            return "其他"
        df = df[df["os"].apply(_norm) == os_choice]
    if country_choice != "全部" and "country" in df.columns:
        df = df[df["country"] == country_choice]
    return df


def _meta_breadcrumb() -> None:
    """可點的麵包屑：每一層是一顆按鈕，點了直接跳回該層。"""
    ss = st.session_state
    crumbs = [("Meta Campaign", "root")]
    if ss.meta_drill_campaign:
        crumbs.append((str(ss.meta_drill_campaign), "campaign"))
    if ss.meta_drill_ad_group:
        crumbs.append((str(ss.meta_drill_ad_group), "ad_group"))

    # 按鈕寬度按字數分配，最後留一欄空白，避免最後一顆被拉得很寬
    widths = [max(len(t) * 0.55 + 2.2, 4.5) for t, _ in crumbs]
    cols = st.columns(widths + [max(6.0, 20 - sum(widths))])
    for i, (text, level) in enumerate(crumbs):
        last = i == len(crumbs) - 1
        label = text if len(text) <= 26 else text[:25] + "…"
        with cols[i]:
            if last:
                # 目前所在層級不做成按鈕，只標示位置
                st.markdown(
                    f'<div style="padding:6px 0;font-size:13px;font-weight:600;'
                    f'color:{theme.TEXT}">{html.escape(label)}</div>',
                    unsafe_allow_html=True)
            elif st.button(f"{label}", key=f"crumb_{level}", width='stretch'):
                if level == "root":
                    ss.meta_drill_campaign = None
                ss.meta_drill_ad_group = None
                st.rerun()


def deep_dive_meta(date_start, date_end, os_choice="全部", country_choice="全部") -> None:
    """Meta 三層下鑽：Campaign → Ad Group → 素材。

    互動規則：點一列＝看走勢（不換層），要換層按「查看…」按鈕，
    麵包屑可以直接跳回上層。
    """
    df = load_meta_raw()
    if df.empty:
        st.info("Meta_raw 無資料")
        return
    df = df[(df["date"].dt.date >= date_start) & (df["date"].dt.date <= date_end)]
    df = _apply_raw_filters(df, os_choice, country_choice)
    if df.empty:
        st.info("此期間 Meta 無資料（可能受篩選影響）")
        return

    ss = st.session_state
    ss.setdefault("meta_drill_campaign", None)
    ss.setdefault("meta_drill_ad_group", None)

    # 目前在哪一層：決定資料範圍、分組欄位、下一層的名稱
    if ss.meta_drill_campaign is None:
        sub, group_col, label, next_label = df, "campaign", "Campaign", "Ad Group"
    elif ss.meta_drill_ad_group is None:
        sub = df[df["campaign"] == ss.meta_drill_campaign]
        group_col, label, next_label = "ad_group", "Ad Group", "素材"
    else:
        sub = df[(df["campaign"] == ss.meta_drill_campaign)
                 & (df["ad_group"] == ss.meta_drill_ad_group)]
        group_col, label, next_label = "ad", "素材 (Ad)", None

    _meta_breadcrumb()

    if sub.empty or group_col not in sub.columns:
        st.warning(f"這一層沒有 {label} 資料")
        return

    stats = _meta_metrics(sub, group_col)
    has_status = False
    if group_col == "ad":
        status_map = _latest_status_map(sub, "ad")
        stats["status_zh"] = stats["ad"].map(lambda x: _status_zh(status_map.get(x, "")))
        has_status = True
    stats = _add_cpi_trend_cols(stats, sub, group_col)

    mode = st.segmented_control("快篩", QUICK_MODES, default="全部",
                                key=f"qf_meta_{group_col}") or "全部"
    view = _quick_filter(stats, mode)
    if view.empty:
        st.info(f"「{mode}」條件下沒有項目。")
        return
    if mode != "全部":
        st.caption(f"{mode}：{len(view)} / {len(stats)} 個 {label}")

    sel = grid.data_grid(view, _level_columns(group_col, label, has_status),
                         key=f"grid_meta_{group_col}", selection="multi")
    names = grid.selected_values(sel, group_col)

    # 下鑽：選中單一項目且還有下一層時才出現
    if next_label and len(names) == 1:
        if st.button(f"查看「{str(names[0])[:26]}」的 {next_label} →",
                     key=f"drill_{group_col}", type="primary"):
            if group_col == "campaign":
                ss.meta_drill_campaign = names[0]
            else:
                ss.meta_drill_ad_group = names[0]
            st.rerun()

    _selection_charts(sub, group_col, names)


_MATCH_TYPE_DISPLAY = {
    "exact": "精準匹配",
    "broad": "廣泛匹配",
    "search_match": "搜尋媒合",
    "搜尋媒合": "搜尋媒合",
}


def _match_type_zh(s: str) -> str:
    if not s or pd.isna(s) or str(s).strip() == "":
        return "(未填)"
    return _MATCH_TYPE_DISPLAY.get(str(s).strip().lower(), str(s))


def deep_dive_asa(date_start, date_end, os_choice="全部", country_choice="全部") -> None:
    """ASA 關鍵字與搜尋詞表現。"""
    df = load_asa_raw()
    if df.empty:
        st.info("ASA_raw 無資料")
        return
    df = df[(df["date"].dt.date >= date_start) & (df["date"].dt.date <= date_end)]
    df = _apply_raw_filters(df, os_choice, country_choice)
    if df.empty:
        st.info("此期間 ASA 無資料（可能受篩選影響）")
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        campaign_opts = ["全部 Campaign"] + sorted(df["campaign"].unique().tolist())
        sel_cmp = st.selectbox("Campaign", campaign_opts, key="asa_cmp_filter")
    with c2:
        if "match_type" in df.columns:
            mt_raw = sorted(df["match_type"].dropna().unique().tolist())
            mt_opts = ["全部"] + [_match_type_zh(m) for m in mt_raw]
            mt_label_to_raw = {_match_type_zh(m): m for m in mt_raw}
            sel_mt = st.segmented_control(
                "Match Type", mt_opts, default="全部", key="asa_mt_filter") or "全部"
        else:
            sel_mt = "全部"

    df_f = df.copy()
    if sel_cmp != "全部 Campaign":
        df_f = df_f[df_f["campaign"] == sel_cmp]
    if sel_mt != "全部" and "match_type" in df_f.columns:
        df_f = df_f[df_f["match_type"] == mt_label_to_raw.get(sel_mt, sel_mt)]
    if df_f.empty:
        st.warning("篩選後無資料")
        return

    st.markdown(theme.section("關鍵字排行", "前 30 名依花費排序；點一列看走勢"),
                unsafe_allow_html=True)
    if "keyword" in df_f.columns:
        kw = _add_cpi_trend_cols(_meta_metrics(df_f, "keyword"), df_f, "keyword")
        kw = kw.head(30)
        sel = grid.data_grid(kw, _level_columns("keyword", "關鍵字", False),
                             key="grid_asa_keyword", selection="multi")
        _selection_charts(df_f, "keyword", grid.selected_values(sel, "keyword"))

    st.markdown(theme.section("搜尋詞表現", "前 30 名，依花費排序"),
                unsafe_allow_html=True)
    if "search_term" in df_f.columns:
        stm = df_f.groupby("search_term").agg(
            spend=("spend", "sum"),
            installs=("installs", "sum"),
        ).reset_index()
        stm = stm[stm["spend"] > 0].sort_values("spend", ascending=False).head(30)
        stm["cpi"] = (stm["spend"] / stm["installs"]).replace(
            [float("inf"), float("-inf")], 0).fillna(0).round(2)
        stm["spend"] = stm["spend"].round(0)
        grid.data_grid(
            stm[["search_term", "spend", "installs", "cpi"]],
            [
                grid.col("search_term", "搜尋詞", flex=2, pinned="left"),
                grid.col("spend", "花費 ($)", "money", width=120),
                grid.col("installs", "安裝", "int", width=100),
                grid.col("cpi", "CPI", "cost", width=96),
            ],
            key="grid_asa_term", selection="none")


def _google_network_table(df: pd.DataFrame) -> None:
    """Network 對比（唯讀）：搜尋 / 多媒體聯播網 / YouTube / 搜尋夥伴。"""
    g = _meta_metrics(df, "network")
    if g.empty:
        st.info("無資料")
        return
    grid.data_grid(
        g[["network", "spend", "impressions", "cpm", "clicks", "ctr",
           "installs", "cpi", "cvr"]],
        [
            grid.col("network", "Network", flex=2, pinned="left"),
            grid.col("spend", "花費 ($)", "money", width=118),
            grid.col("impressions", "曝光", "int", width=110),
            grid.col("cpm", "CPM", "cost", width=92),
            grid.col("clicks", "點擊", "int", width=100),
            grid.col("ctr", "CTR", "pct", width=88),
            grid.col("installs", "安裝", "int", width=96),
            grid.col("cpi", "CPI", "cost", width=92),
            grid.col("cvr", "CVR", "pct", width=88),
        ],
        key="grid_google_network", selection="none")


def deep_dive_google(date_start, date_end, os_choice="全部", country_choice="全部") -> None:
    """Google 各 Network 與 Ad Group 表現。"""
    df = load_google_raw()
    if df.empty:
        st.info("Google_raw 無資料")
        return
    df = df[(df["date"].dt.date >= date_start) & (df["date"].dt.date <= date_end)]
    df = _apply_raw_filters(df, os_choice, country_choice)
    if df.empty:
        st.info("此期間 Google 無資料（可能受篩選影響）")
        return

    st.markdown(theme.section("Network 對比", "搜尋 / 多媒體聯播網 / YouTube / 搜尋夥伴"),
                unsafe_allow_html=True)
    if "network" in df.columns:
        _google_network_table(df)

    st.markdown(theme.section("Ad Group 排行", "前 30 名依花費排序；點一列看走勢"),
                unsafe_allow_html=True)
    if "ad_group" in df.columns:
        ag = _add_cpi_trend_cols(_meta_metrics(df, "ad_group"), df, "ad_group")
        ag = ag.head(30)
        sel = grid.data_grid(ag, _level_columns("ad_group", "Ad Group", False),
                             key="grid_google_adgroup", selection="multi")
        _selection_charts(df, "ad_group", grid.selected_values(sel, "ad_group"))


# ──────────────────────────────────────────────────────────────────────
#  主程式
# ──────────────────────────────────────────────────────────────────────

# ── 資料載入 ──────────────────────────────────────────────────────
with st.spinner("讀取 Google Sheet 資料…"):
    df_raw = load_unified()

_failed_tabs = list(getattr(df_raw, "attrs", {}).get("failed_tabs", []))
if df_raw is None or df_raw.empty:
    st.error("無法載入資料，請檢查 Google Sheet 連線設定。")
    if _failed_tabs:
        st.caption("失敗明細：" + "；".join(f"{t}（{e}）" for _m, t, e in _failed_tabs))
    st.stop()

# 少讀到某家媒體時要講清楚：此時下面所有 KPI 都不含那家的花費與安裝，
# 靜靜跳過會讓人拿殘缺數字做決策。
if _failed_tabs:
    _miss = "、".join(m for m, _t, _e in _failed_tabs)
    st.error(
        f"**資料不完整：{_miss} 讀取失敗** ─ 以下所有數字都不含這些媒體，"
        f"請點左側「重新載入資料」重試。\n\n"
        + "\n".join(f"- `{t}`：{e}" for _m, t, e in _failed_tabs)
    )

# ── 主導覽（sidebar 上半）────────────────────────────────────────
# 新增功能往 NAV_ITEMS 加一項即可，自動往下堆疊。
NAV_ITEMS = [
    ("廣告數據", "廣告數據"),
    ("行事曆・待辦", "行事曆待辦"),
]
_VALID_SECTIONS = {v for _, v in NAV_ITEMS}
# 目前功能同步寫進網址 query param：雲端免費版連線重連或使用者重整時
# session_state 可能被清空，此時從網址還原，避免「操作後跳回廣告數據」。
if "_main_section" not in st.session_state:
    _q = st.query_params.get("view")
    st.session_state["_main_section"] = _q if _q in _VALID_SECTIONS else "廣告數據"

with st.sidebar:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:9px;margin-bottom:14px">'
        f'<div style="width:26px;height:26px;border-radius:7px;flex-shrink:0;'
        f'background:linear-gradient(135deg,{theme.ACCENT} 0%,{theme.ACCENT_DEEP} 100%)"></div>'
        f'<div><div style="font-size:13.5px;font-weight:700;color:{theme.TEXT};'
        f'line-height:1.2">Ocean Fishooter</div>'
        f'<div style="font-size:10.5px;color:{theme.TEXT_DIM}">UA Dashboard</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    for _label, _val in NAV_ITEMS:
        if st.button(_label, width='stretch', key=f"nav_{_val}",
                     type="primary" if st.session_state["_main_section"] == _val
                     else "secondary"):
            st.session_state["_main_section"] = _val
            st.query_params["view"] = _val
            st.rerun()

section = st.session_state["_main_section"]
if st.query_params.get("view") != section:
    st.query_params["view"] = section

# 行事曆・待辦模式：主畫面只渲染行事曆，st.stop 跳過所有廣告區塊
if section == "行事曆待辦":
    st.markdown("## 行事曆 / 待辦")
    render_calendar_todo()
    st.stop()

# ── 篩選（sidebar 下半）──────────────────────────────────────────
min_date, max_date = df_raw["date"].min(), df_raw["date"].max()
min_d_date, max_d_date = min_date.date(), max_date.date()


def _norm_os(s):
    """把各家寫法不一的 OS 欄位收斂成 iOS / Android / 其他。"""
    s = str(s).strip().upper()
    if s in ("IOS", "I"):
        return "iOS"
    if s in ("AND", "ANDROID"):
        return "Android"
    return "其他"


df_raw["_os_group"] = df_raw["os"].apply(_norm_os)
all_country = sorted(df_raw["country"].dropna().unique().tolist())
all_media = sorted(df_raw["media"].dropna().unique().tolist())

with st.sidebar:
    st.markdown("---")
    st.markdown(
        f'<div style="font-size:10.5px;font-weight:700;color:{theme.TEXT_DIM};'
        f'letter-spacing:.8px;margin-bottom:6px">篩選條件</div>',
        unsafe_allow_html=True,
    )
    # segmented_control 可以被點成未選取（回傳 None），一律用 or 補回預設值
    date_mode = st.segmented_control(
        "期間", ["本月", "近 7 天", "近 14 天", "昨日", "自訂"],
        default="本月", key="f_date_mode") or "本月"
    if date_mode == "自訂":
        if "date_picker" not in st.session_state:
            _ds = max(max_d_date.replace(day=1), min_d_date)
            st.session_state["date_picker"] = (_ds, max_d_date)
        date_range = st.date_input(
            "自訂範圍", key="date_picker",
            min_value=min_d_date, max_value=max_d_date,
        )
    else:
        end = max_d_date
        if date_mode == "昨日":
            start = end
        elif date_mode == "近 7 天":
            start = end - timedelta(days=6)
        elif date_mode == "近 14 天":
            start = end - timedelta(days=13)
        else:  # 本月
            start = end.replace(day=1)
        date_range = (max(start, min_d_date), end)

    media_choice = st.segmented_control(
        "媒體", ["全部"] + all_media, default="全部", key="f_media") or "全部"
    os_choice = st.segmented_control(
        "OS", ["全部", "iOS", "Android", "其他"], default="全部",
        key="f_os") or "全部"
    country_choice = st.selectbox(
        "國家", ["全部"] + all_country, index=0, key="f_country")

    st.markdown("---")
    # 資料新鮮度：超過一天沒進新資料就要看得出來
    days_behind = (datetime.now().date() - max_date.date()).days
    if days_behind <= 1:
        _lv, _txt = "pos", "正常"
    elif days_behind <= 3:
        _lv, _txt = "warn", "稍舊"
    else:
        _lv, _txt = "neg", "過期"
    st.markdown(
        theme.status_card("資料狀態", max_date.strftime("%Y-%m-%d"),
                          f"距今 {days_behind} 天（{_txt}）", _lv),
        unsafe_allow_html=True,
    )
    st.caption(f"資料範圍 {min_date.strftime('%Y-%m-%d')} ~ "
               f"{max_date.strftime('%Y-%m-%d')}")
    st.caption(f"頁面開啟 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if st.button("重新載入資料", width='stretch',
                 help="清除快取並從 Google Sheet 重新拉資料"):
        st.cache_data.clear()
        st.rerun()

# ── 套用篩選 ─────────────────────────────────────────────────────
df = df_raw.copy()
df_prev = pd.DataFrame()
period_txt, prev_txt = "", ""
if len(date_range) == 2:
    start, end = date_range[0], date_range[1]
    df = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]
    # 對比期＝緊鄰前一段、同樣長度的期間
    period_len = (end - start).days + 1
    prev_end = start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=period_len - 1)
    df_prev = df_raw[(df_raw["date"].dt.date >= prev_start)
                     & (df_raw["date"].dt.date <= prev_end)]
    period_txt = (f"{start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}"
                  f"（{period_len} 天）")
    prev_txt = (f"對比 {prev_start.strftime('%m-%d')} ~ "
                f"{prev_end.strftime('%m-%d')}")

if os_choice != "全部":
    df = df[df["_os_group"] == os_choice]
    df_prev = df_prev[df_prev["_os_group"] == os_choice] if not df_prev.empty else df_prev
if country_choice != "全部":
    df = df[df["country"] == country_choice]
    df_prev = df_prev[df_prev["country"] == country_choice] if not df_prev.empty else df_prev
if media_choice != "全部":
    df = df[df["media"] == media_choice]
    df_prev = df_prev[df_prev["media"] == media_choice] if not df_prev.empty else df_prev

# ── 頂部檢視列 ───────────────────────────────────────────────────
_chips = (theme.chip("媒體", html.escape(media_choice), media_choice != "全部")
          + theme.chip("國家", html.escape(country_choice), country_choice != "全部")
          + theme.chip("OS", html.escape(os_choice), os_choice != "全部"))
st.markdown(
    f'<div class="of-topbar">'
    f'<div><div class="of-topbar-title">廣告投放總覽</div>'
    f'<div class="of-topbar-sub">{period_txt}　{prev_txt}</div></div>'
    f'<div class="of-topbar-spacer"></div>'
    f'<div class="of-chips">{_chips}</div></div>',
    unsafe_allow_html=True,
)

# ── 分頁 ─────────────────────────────────────────────────────────
tab_overview, tab_media, tab_geo, tab_deep = st.tabs([
    "投放總覽", "媒體對比", "地區・OS", "媒體深度",
])

with tab_overview:
    show_kpis(df, df_prev)

    st.markdown(theme.section("異常警示", "與對比期比較後值得看一眼的變化"),
                unsafe_allow_html=True)
    show_alerts(df, df_prev)

    st.markdown(theme.section("每日趨勢", "柱＝花費，線＝安裝與 CPI，▲＝當天有廣告操作"),
                unsafe_allow_html=True)
    _ops = get_filtered_ops(date_range, media_choice)
    show_daily_trend(df, _ops)

    st.markdown(theme.section("媒體分布"), unsafe_allow_html=True)
    show_media_mix(df)

    st.markdown(theme.section("期間內廣告操作", "完整備註在「行事曆・待辦」"),
                unsafe_allow_html=True)
    show_ops_log(_ops)

with tab_media:
    st.markdown(theme.section("六媒體對比", "點欄位標題可依該欄排序"),
                unsafe_allow_html=True)
    show_media_compare(df)

with tab_geo:
    show_geo_os(df)

with tab_deep:
    deep_media = st.segmented_control(
        "媒體", ["Meta", "ASA", "Google", "TikTok", "Applovin", "Moloco"],
        default="Meta", key="deep_tab", label_visibility="collapsed") or "Meta"

    if deep_media == "Meta":
        # Meta 有 Campaign → Ad Group → 素材 三層下鑽
        if len(date_range) == 2:
            deep_dive_meta(date_range[0], date_range[1], os_choice, country_choice)
        else:
            st.warning("請選擇完整日期範圍")
    else:
        st.markdown(theme.section(f"{deep_media} Campaign 排行",
                                  "點一列看走勢，Ctrl 複選可做對比"),
                    unsafe_allow_html=True)
        _sub, _picked = show_campaign_table(df, deep_media,
                                            key=f"grid_cmp_{deep_media}")
        _selection_charts(_sub, "campaign", _picked)

        # ASA 與 Google 另有各自的獨家欄位（關鍵字 / Network），
        # TikTok、Applovin、Moloco 只到 campaign 層。
        if len(date_range) == 2:
            if deep_media == "ASA":
                deep_dive_asa(date_range[0], date_range[1], os_choice, country_choice)
            elif deep_media == "Google":
                deep_dive_google(date_range[0], date_range[1], os_choice, country_choice)
