# -*- coding: utf-8 -*-
"""OFmedia 廣告儀表板(雲端版)

資料源:OceanFishooter 廣告儀表板 Google Sheet 的 6 個 _raw 分頁
頁籤:投放總覽 / 媒體成效 / 地區 OS / Campaign 表現 / 媒體深度
"""
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from auth import require_password
from data import (load_unified, load_meta_raw, load_asa_raw,
                  load_google_raw, RAW_TABS)

st.set_page_config(
    page_title="Ocean Fishooter 廣告儀表板",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_password()

# 媒體配色(維持品牌色感)
MEDIA_COLORS = {
    "Meta": "#1877F2",
    "ASA": "#999999",
    "Google": "#4285F4",
    "TikTok": "#000000",
    "Applovin": "#FF5C5C",
    "Moloco": "#7C3AED",
}

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


def _sparkline_svg(values: list, color: str = "#60A5FA") -> str:
    if not values or len(values) < 2:
        return ""
    width, height, pad = 90, 40, 4
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        max_v = min_v + 1
    pts = []
    for i, v in enumerate(values):
        x = i * width / (len(values) - 1)
        y = height - pad - (v - min_v) / (max_v - min_v) * (height - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    last_x = (len(values) - 1) * width / (len(values) - 1)
    last_y = float(pts[-1].split(",")[1])
    return (
        f'<svg width="{width}" height="{height}" '
        f'style="display:block;opacity:0.8;flex-shrink:0">'
        f'<polyline points="{" ".join(pts)}" stroke="{color}" stroke-width="1.8" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.5" fill="{color}"/>'
        f'</svg>'
    )


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


_KPI_CSS = """
<style>
.kpi-card{
    background:#1E293B;border:1px solid #334155;border-radius:10px;
    padding:10px 14px;margin-bottom:10px;
    box-shadow:0 1px 3px rgba(0,0,0,0.3);
    display:flex;align-items:center;gap:10px;min-height:84px;
}
.kpi-vol{background:linear-gradient(135deg,#1E3A5F 0%,#1E293B 100%);border-color:#3B82F6}
.kpi-rate{background:linear-gradient(135deg,#3F2A0E 0%,#1E293B 100%);border-color:#D97706}
.kpi-body{flex:1;min-width:0}
.kpi-label{font-size:13.5px;font-weight:600;color:#CBD5E1;margin-bottom:2px}
.kpi-value{font-size:22px;font-weight:700;color:#F8FAFC;line-height:1.1}
.kpi-delta{font-size:11.5px;margin-top:3px;font-weight:500}
.kpi-up-good{color:#4ADE80}
.kpi-down-good{color:#F87171}
.kpi-up-bad{color:#F87171}
.kpi-down-bad{color:#4ADE80}
.kpi-section{font-size:15px;font-weight:700;margin:14px 0 8px 0;color:#F1F5F9}
</style>
"""


def show_kpis(df: pd.DataFrame, df_prev: pd.DataFrame = None) -> None:
    curr = _kpi_pack(df)
    prev = _kpi_pack(df_prev) if df_prev is not None and not df_prev.empty else None
    sparks = _compute_sparks(df)

    st.markdown(_KPI_CSS, unsafe_allow_html=True)

    def render(label, value, key, category, inverse=False, color="#60A5FA"):
        delta_html = ""
        if prev and prev.get(key):
            pct = (curr[key] - prev[key]) / prev[key] * 100
            arrow = "↑" if pct >= 0 else "↓"
            sign = "+" if pct >= 0 else ""
            is_up = pct >= 0
            cls = ("kpi-up-bad" if is_up else "kpi-down-bad") if inverse else \
                  ("kpi-up-good" if is_up else "kpi-down-good")
            delta_html = f'<div class="kpi-delta {cls}">{arrow} {sign}{pct:.1f}% vs 上期</div>'
        spark_html = _sparkline_svg(sparks.get(key, []), color=color)
        return (
            f'<div class="kpi-card kpi-{category}">'
            f'<div class="kpi-body">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>'
            f'{delta_html}'
            f'</div>'
            f'{spark_html}'
            f'</div>'
        )

    # 規模指標(藍)── 4 個並排
    st.markdown('<div class="kpi-section">💵 規模指標</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(render("💰 花費", f"${curr['spend']:,.0f}", "spend", "vol"),
                unsafe_allow_html=True)
    c2.markdown(render("👁️ 曝光", f"{curr['imp']:,.0f}", "imp", "vol"),
                unsafe_allow_html=True)
    c3.markdown(render("🖱️ 點擊", f"{curr['clicks']:,.0f}", "clicks", "vol"),
                unsafe_allow_html=True)
    c4.markdown(render("📲 安裝", f"{curr['installs']:,.0f}", "installs", "vol"),
                unsafe_allow_html=True)

    # 效率指標(黃)── 4 個並排,跟上排對齊
    st.markdown('<div class="kpi-section">🎯 效率指標</div>', unsafe_allow_html=True)
    c5, c6, c7, c8 = st.columns(4)
    c5.markdown(render("📡 CPM", f"${curr['cpm']:.2f}", "cpm", "rate",
                       inverse=True, color="#FBBF24"), unsafe_allow_html=True)
    c6.markdown(render("📣 CTR", f"{curr['ctr']:.2f}%", "ctr", "rate",
                       color="#FBBF24"), unsafe_allow_html=True)
    c7.markdown(render("🔁 CVR", f"{curr['cvr']:.2f}%", "cvr", "rate",
                       color="#FBBF24"), unsafe_allow_html=True)
    c8.markdown(render("💎 CPI", f"${curr['cpi']:.2f}" if curr['cpi'] > 0 else "—",
                       "cpi", "rate", inverse=True, color="#FBBF24"),
                unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────
#  圖表
# ──────────────────────────────────────────────────────────────────────
def show_daily_trend(df: pd.DataFrame) -> None:
    daily = df.groupby("date").agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
    ).reset_index()
    daily["cpi"] = (daily["spend"] / daily["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["date"], y=daily["spend"], name="花費",
        marker_color="#60A5FA", opacity=0.6, yaxis="y1",
        hovertemplate="💰 $%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["installs"], name="安裝",
        mode="lines+markers", line=dict(color="#F1F5F9", width=2.5),
        marker=dict(size=6), yaxis="y2",
        hovertemplate="📲 %{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["cpi"], name="CPI",
        mode="lines+markers", line=dict(color="#F87171", width=2.5, dash="dot"),
        marker=dict(size=6), yaxis="y3",
        hovertemplate="💎 $%{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=380, hovermode="x unified",
        margin=dict(t=40, b=20, l=10, r=80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor="#334155", domain=[0, 0.92],
                   tickformat="%m/%d"),
        yaxis=dict(title=dict(text="花費 ($)", font=dict(color="#60A5FA")),
                   showgrid=True, gridcolor="#334155",
                   tickfont=dict(color="#60A5FA")),
        yaxis2=dict(title=dict(text="安裝", font=dict(color="#F1F5F9")),
                    overlaying="y", side="right", showgrid=False,
                    position=0.92, tickfont=dict(color="#F1F5F9")),
        yaxis3=dict(title=dict(text="CPI ($)", font=dict(color="#F87171")),
                    overlaying="y", side="right", showgrid=False,
                    anchor="free", position=1.0,
                    tickfont=dict(color="#F87171")),
    )
    st.plotly_chart(fig, use_container_width=True)


def show_media_mix(df: pd.DataFrame) -> None:
    media_stats = df.groupby("media").agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
    ).reset_index()
    media_stats["cpi"] = (media_stats["spend"] / media_stats["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.pie(media_stats, values="spend", names="media",
                     title="花費分布", color="media",
                     color_discrete_map=MEDIA_COLORS, hole=0.4)
        fig.update_layout(template="plotly_dark", height=320,
                          paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)",
                          margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.pie(media_stats, values="installs", names="media",
                      title="安裝分布", color="media",
                      color_discrete_map=MEDIA_COLORS, hole=0.4)
        fig2.update_layout(template="plotly_dark", height=320,
                           paper_bgcolor="rgba(0,0,0,0)",
                           plot_bgcolor="rgba(0,0,0,0)",
                           margin=dict(t=40, b=10))
        st.plotly_chart(fig2, use_container_width=True)


def show_alerts(df: pd.DataFrame, df_prev: pd.DataFrame = None) -> None:
    alerts = []
    if df_prev is not None and not df_prev.empty:
        # 媒體 CPI 暴增
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
                if chg > 30:
                    alerts.append(("⚠️", "CPI 暴增",
                                   f"**{r['media']}** CPI 從 ${r['cpi_prev']:.2f} → "
                                   f"${r['cpi']:.2f}({chg:+.0f}%),建議檢查素材或受眾"))
                elif chg < -25 and r["installs"] > 50:
                    alerts.append(("🌟", "CPI 改善",
                                   f"**{r['media']}** CPI 從 ${r['cpi_prev']:.2f} → "
                                   f"${r['cpi']:.2f}({chg:+.0f}%),可考慮加碼"))
        # 安裝量驟降
        cv = df.groupby("media")["installs"].sum()
        pv = df_prev.groupby("media")["installs"].sum()
        for media in cv.index:
            if media in pv.index and pv[media] > 50:
                chg = (cv[media] - pv[media]) / pv[media] * 100
                if chg < -40:
                    alerts.append(("📉", "安裝量驟降",
                                   f"**{media}** 安裝從 {pv[media]:.0f} → "
                                   f"{cv[media]:.0f}({chg:+.0f}%)"))

    # 預算過度集中
    media_spend = df.groupby("media")["spend"].sum().reset_index()
    total = media_spend["spend"].sum()
    for _, r in media_spend.iterrows():
        pct = r["spend"] / total * 100 if total > 0 else 0
        if pct > 60:
            alerts.append(("⚠️", "預算集中",
                           f"**{r['media']}** 佔總花費 {pct:.1f}%,單一媒體依賴風險高"))

    if alerts:
        for icon, cat, msg in alerts:
            is_warning = "⚠️" in icon or "📉" in icon
            bg = "#3F2A0E" if is_warning else "#0F3A1F"
            border = "#D97706" if is_warning else "#16A34A"
            txt = "#FCD34D" if is_warning else "#86EFAC"
            st.markdown(
                f"<div style='background:{bg};padding:10px 15px;border-radius:8px;"
                f"border-left:3px solid {border};margin-bottom:6px;color:#F1F5F9'>"
                f"{icon} <b style='color:{txt}'>[{cat}]</b> {msg}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success("目前無重大警示。")


def show_media_compare(df: pd.DataFrame) -> None:
    """6 媒體並排對比表 + CPI 排行條形圖。"""
    stats = df.groupby("media").agg(
        spend=("spend", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        installs=("installs", "sum"),
    ).reset_index()
    stats["CTR(%)"] = (stats["clicks"] / stats["impressions"] * 100).fillna(0).round(2)
    stats["CPC($)"] = (stats["spend"] / stats["clicks"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    stats["CPI($)"] = (stats["spend"] / stats["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    total_spend = stats["spend"].sum()
    stats["花費%"] = (stats["spend"] / total_spend * 100).round(1) if total_spend > 0 else 0

    disp = stats[["media", "spend", "花費%", "installs", "CPI($)", "CTR(%)", "CPC($)"]].copy()
    disp.columns = ["媒體", "花費($)", "花費%", "安裝", "CPI($)", "CTR(%)", "CPC($)"]
    disp = disp.sort_values("花費($)", ascending=False)
    disp["花費($)"] = disp["花費($)"].apply(lambda x: f"${x:,.0f}")
    disp["安裝"] = disp["安裝"].apply(lambda x: f"{int(x):,}")
    disp["花費%"] = disp["花費%"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(disp, hide_index=True, use_container_width=True)

    # CPI 排行
    rank = stats[stats["installs"] >= 10].sort_values("CPI($)", ascending=False)
    if not rank.empty:
        fig = px.bar(rank, x="CPI($)", y="media", orientation="h",
                     color="media", color_discrete_map=MEDIA_COLORS,
                     title="CPI 排行(數字越低越好,>10 安裝才列入)")
        fig.update_layout(height=300, showlegend=False, plot_bgcolor="white",
                          margin=dict(t=40, b=10),
                          yaxis={"categoryorder": "total descending"})
        st.plotly_chart(fig, use_container_width=True)


def show_geo_os(df: pd.DataFrame) -> None:
    """地區 + OS 分析。"""
    # iOS vs Android 兩個 KPI 並排
    st.subheader("📱 iOS vs Android")
    df_ios = df[df["os"].str.upper().isin(["IOS"])]
    df_and = df[df["os"].str.upper().isin(["AND", "ANDROID"])]
    c1, c2 = st.columns(2)
    for col, sub, label, emoji in [(c1, df_ios, "iOS", "🍎"),
                                    (c2, df_and, "Android", "🤖")]:
        with col:
            k = _kpi_pack(sub)
            st.markdown(
                f"<div style='padding:14px;background:#F8F9FA;border-radius:10px;"
                f"border:1px solid #E5E7EB'>"
                f"<div style='font-size:14px;font-weight:700;color:#1F2937;"
                f"margin-bottom:8px'>{emoji} {label}</div>"
                f"<div style='font-size:13px;line-height:1.8'>"
                f"💰 花費:<b>${k['spend']:,.0f}</b><br>"
                f"📲 安裝:<b>{k['installs']:,.0f}</b><br>"
                f"💎 CPI:<b>${k['cpi']:.2f}</b><br>"
                f"📣 CTR:<b>{k['ctr']:.2f}%</b><br>"
                f"🔁 CVR:<b>{k['cvr']:.2f}%</b>"
                f"</div></div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.subheader("🌍 國家表現(前 15 名,依花費排)")
    geo = df.groupby("country").agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
        clicks=("clicks", "sum"),
    ).reset_index()
    geo["CPI($)"] = (geo["spend"] / geo["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    geo["CPC($)"] = (geo["spend"] / geo["clicks"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    top15 = geo.sort_values("spend", ascending=False).head(15).copy()
    top15["花費($)"] = top15["spend"].apply(lambda x: f"${x:,.0f}")
    top15["安裝"] = top15["installs"].apply(lambda x: f"{int(x):,}")
    disp = top15[["country", "花費($)", "安裝", "CPI($)", "CPC($)"]]
    disp.columns = ["國家", "花費($)", "安裝", "CPI($)", "CPC($)"]
    st.dataframe(disp, hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("🌡️ 國家 × 媒體 CPI 熱力矩陣")
    heatmap_df = df.copy()
    heatmap_df = heatmap_df[heatmap_df["country"].isin(top15["country"].tolist())]
    pivot = heatmap_df.pivot_table(index="country", columns="media",
                                    values=["spend", "installs"], aggfunc="sum",
                                    fill_value=0)
    if not pivot.empty:
        cpi_mat = pivot["spend"] / pivot["installs"].replace(0, float("nan"))
        cpi_mat = cpi_mat.round(2)
        fig = px.imshow(cpi_mat, color_continuous_scale="RdYlGn_r",
                        labels=dict(color="CPI ($)"), aspect="auto",
                        text_auto=".2f")
        fig.update_layout(height=400, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("綠 = CPI 低(便宜的安裝),紅 = CPI 高;空格代表該組合無安裝")


def show_campaign_table(df: pd.DataFrame, media_filter: str = "全部") -> None:
    """Campaign 排行 + 異常警示。"""
    if media_filter != "全部":
        df = df[df["media"] == media_filter]
    if df.empty:
        st.info("此條件下無資料")
        return
    cmp = df.groupby(["media", "campaign"]).agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
    ).reset_index()
    cmp["CPI($)"] = (cmp["spend"] / cmp["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    cmp["CTR(%)"] = (cmp["clicks"] / cmp["impressions"] * 100).fillna(0).round(2)
    cmp = cmp.sort_values("spend", ascending=False)

    # 異常標註
    media_avg_cpi = cmp.groupby("media").apply(
        lambda g: g[g["installs"] >= 10]["CPI($)"].mean() if len(g) else 0
    ).to_dict()

    def label_row(r):
        if r["installs"] < 5 and r["spend"] > 100:
            return "🚨 高花費低安裝"
        avg = media_avg_cpi.get(r["media"], 0)
        if avg > 0 and r["installs"] >= 10:
            if r["CPI($)"] < avg * 0.7:
                return "💎 優於均值 30%+"
            if r["CPI($)"] > avg * 1.5:
                return "⚠️ 高於均值 50%+"
        return ""

    cmp["標註"] = cmp.apply(label_row, axis=1)

    disp = cmp[["media", "campaign", "spend", "installs", "CPI($)", "CTR(%)", "標註"]].copy()
    disp.columns = ["媒體", "Campaign", "花費($)", "安裝", "CPI($)", "CTR(%)", "標註"]
    disp["花費($)"] = disp["花費($)"].apply(lambda x: f"${x:,.0f}")
    disp["安裝"] = disp["安裝"].apply(lambda x: f"{int(x):,}")
    st.dataframe(disp, hide_index=True, use_container_width=True, height=460)


# ──────────────────────────────────────────────────────────────────────
#  深度頁籤
# ──────────────────────────────────────────────────────────────────────
def _meta_metrics(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """共用:計算 Meta drill-down 各層級的標準指標(花費/安裝/CPI/CTR/CVR/CPM)。"""
    g = df.groupby(group_col).agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
    ).reset_index()
    g["CPI($)"] = (g["spend"] / g["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    g["CTR(%)"] = (g["clicks"] / g["impressions"] * 100).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    g["CVR(%)"] = (g["installs"] / g["clicks"] * 100).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    g["CPM($)"] = (g["spend"] / g["impressions"] * 1000).replace(
        [float("inf"), float("-inf")], 0).fillna(0).round(2)
    return g.sort_values("spend", ascending=False)


def _meta_render_table(stats: pd.DataFrame, key_col: str, label: str, table_key: str) -> int:
    """顯示帶選取的 dataframe,回傳被點擊的列索引(-1 = 沒選)。"""
    disp = stats[[key_col, "spend", "installs", "CPI($)", "CTR(%)", "CVR(%)", "CPM($)"]].copy()
    disp.columns = [label, "花費($)", "安裝", "CPI($)", "CTR(%)", "CVR(%)", "CPM($)"]
    disp["花費($)"] = disp["花費($)"].apply(lambda x: f"${x:,.0f}")
    disp["安裝"] = disp["安裝"].apply(lambda x: f"{int(x):,}")
    event = st.dataframe(
        disp,
        hide_index=True,
        use_container_width=True,
        height=460,
        on_select="rerun",
        selection_mode="single-row",
        key=table_key,
    )
    if event and getattr(event, "selection", None):
        rows = event.selection.get("rows", [])
        if rows:
            return rows[0]
    return -1


def deep_dive_meta(date_start, date_end) -> None:
    df = load_meta_raw()
    if df.empty:
        st.info("Meta_raw 無資料")
        return
    df = df[(df["date"].dt.date >= date_start) & (df["date"].dt.date <= date_end)]
    if df.empty:
        st.info("此期間 Meta 無資料")
        return

    ss = st.session_state
    if "meta_drill_campaign" not in ss:
        ss.meta_drill_campaign = None
    if "meta_drill_ad_group" not in ss:
        ss.meta_drill_ad_group = None

    # 麵包屑
    crumbs = ["📦 Campaign"]
    if ss.meta_drill_campaign:
        crumbs.append(f"📁 {ss.meta_drill_campaign}")
    if ss.meta_drill_ad_group:
        crumbs.append(f"🎬 {ss.meta_drill_ad_group}")
    st.markdown(
        f"<div style='padding:8px 12px;background:#1E293B;border-left:3px solid "
        f"#3B82F6;border-radius:6px;margin-bottom:10px;font-size:13px;color:#CBD5E1'>"
        f"{' &nbsp;›&nbsp; '.join(crumbs)}</div>",
        unsafe_allow_html=True,
    )

    # 返回按鈕
    c1, c2 = st.columns([1, 5])
    with c1:
        if ss.meta_drill_ad_group:
            if st.button("← 返回 Ad Group", key="back_ag"):
                ss.meta_drill_ad_group = None
                st.rerun()
        elif ss.meta_drill_campaign:
            if st.button("← 返回 Campaign", key="back_cmp"):
                ss.meta_drill_campaign = None
                st.rerun()

    # ── 第 1 層:Campaign ──
    if ss.meta_drill_campaign is None:
        st.caption("👇 **點任一列查看該 Campaign 的 Ad Group**")
        stats = _meta_metrics(df, "campaign")
        idx = _meta_render_table(stats, "campaign", "Campaign", "tbl_meta_campaign")
        if idx >= 0:
            ss.meta_drill_campaign = stats.iloc[idx]["campaign"]
            st.rerun()

    # ── 第 2 層:Ad Group ──
    elif ss.meta_drill_ad_group is None:
        sub = df[df["campaign"] == ss.meta_drill_campaign]
        st.caption(f"📁 **Campaign:** `{ss.meta_drill_campaign}` ─ 👇 點任一列查看該 Ad Group 的素材")
        if sub.empty or "ad_group" not in sub.columns:
            st.warning("此 Campaign 無 Ad Group 資料")
            return
        stats = _meta_metrics(sub, "ad_group")
        idx = _meta_render_table(stats, "ad_group", "Ad Group", "tbl_meta_ad_group")
        if idx >= 0:
            ss.meta_drill_ad_group = stats.iloc[idx]["ad_group"]
            st.rerun()

    # ── 第 3 層:素材(Ad)──
    else:
        sub = df[
            (df["campaign"] == ss.meta_drill_campaign)
            & (df["ad_group"] == ss.meta_drill_ad_group)
        ]
        st.caption(
            f"📁 **Campaign:** `{ss.meta_drill_campaign}` &nbsp;|&nbsp; "
            f"🎬 **Ad Group:** `{ss.meta_drill_ad_group}`"
        )
        if sub.empty or "ad" not in sub.columns:
            st.warning("此 Ad Group 無素材資料")
            return
        stats = _meta_metrics(sub, "ad")
        disp = stats[["ad", "spend", "installs", "CPI($)", "CTR(%)", "CVR(%)", "CPM($)"]].copy()
        disp.columns = ["素材(Ad)", "花費($)", "安裝", "CPI($)", "CTR(%)", "CVR(%)", "CPM($)"]
        disp["花費($)"] = disp["花費($)"].apply(lambda x: f"${x:,.0f}")
        disp["安裝"] = disp["安裝"].apply(lambda x: f"{int(x):,}")
        st.dataframe(disp, hide_index=True, use_container_width=True, height=460)


def deep_dive_asa(date_start, date_end) -> None:
    df = load_asa_raw()
    if df.empty:
        st.info("ASA_raw 無資料")
        return
    df = df[(df["date"].dt.date >= date_start) & (df["date"].dt.date <= date_end)]
    if df.empty:
        st.info("此期間 ASA 無資料")
        return

    st.subheader("🔑 關鍵字(Keyword)排行 ─ 依花費")
    if "keyword" in df.columns:
        kw = df.groupby("keyword").agg(
            spend=("spend", "sum"),
            installs=("installs", "sum"),
            clicks=("clicks", "sum"),
            impressions=("impressions", "sum"),
        ).reset_index()
        kw["CPI($)"] = (kw["spend"] / kw["installs"]).replace(
            [float("inf"), float("-inf")], 0).fillna(0).round(2)
        kw["CTR(%)"] = (kw["clicks"] / kw["impressions"] * 100).fillna(0).round(2)
        kw["CVR(%)"] = (kw["installs"] / kw["clicks"] * 100).fillna(0).round(2)
        kw = kw.sort_values("spend", ascending=False).head(30)
        kw["花費($)"] = kw["spend"].apply(lambda x: f"${x:,.0f}")
        kw["安裝"] = kw["installs"].apply(lambda x: f"{int(x):,}")
        st.dataframe(kw[["keyword", "花費($)", "安裝", "CPI($)", "CTR(%)", "CVR(%)"]],
                     hide_index=True, use_container_width=True, height=460)

    st.markdown("---")
    st.subheader("🔎 Search Term vs Keyword 表現")
    if "search_term" in df.columns:
        st_df = df.groupby("search_term").agg(
            spend=("spend", "sum"),
            installs=("installs", "sum"),
        ).reset_index()
        st_df = st_df[st_df["spend"] > 0].sort_values("spend", ascending=False).head(20)
        st_df["CPI($)"] = (st_df["spend"] / st_df["installs"]).replace(
            [float("inf"), float("-inf")], 0).fillna(0).round(2)
        st_df["花費($)"] = st_df["spend"].apply(lambda x: f"${x:,.0f}")
        st_df["安裝"] = st_df["installs"].apply(lambda x: f"{int(x):,}")
        st.dataframe(st_df[["search_term", "花費($)", "安裝", "CPI($)"]],
                     hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("📍 Match Type 表現")
    if "match_type" in df.columns:
        mt = df.groupby("match_type").agg(
            spend=("spend", "sum"),
            installs=("installs", "sum"),
            clicks=("clicks", "sum"),
        ).reset_index()
        mt["CPI($)"] = (mt["spend"] / mt["installs"]).replace(
            [float("inf"), float("-inf")], 0).fillna(0).round(2)
        mt["花費($)"] = mt["spend"].apply(lambda x: f"${x:,.0f}")
        mt["安裝"] = mt["installs"].apply(lambda x: f"{int(x):,}")
        st.dataframe(mt[["match_type", "花費($)", "安裝", "CPI($)"]],
                     hide_index=True, use_container_width=True)


def deep_dive_google(date_start, date_end) -> None:
    df = load_google_raw()
    if df.empty:
        st.info("Google_raw 無資料")
        return
    df = df[(df["date"].dt.date >= date_start) & (df["date"].dt.date <= date_end)]
    if df.empty:
        st.info("此期間 Google 無資料")
        return

    st.subheader("🌐 Network 表現對比(搜尋 / 多媒體聯播網)")
    if "network" in df.columns:
        nw = df.groupby("network").agg(
            spend=("spend", "sum"),
            installs=("installs", "sum"),
            clicks=("clicks", "sum"),
            impressions=("impressions", "sum"),
        ).reset_index()
        nw["CPI($)"] = (nw["spend"] / nw["installs"]).replace(
            [float("inf"), float("-inf")], 0).fillna(0).round(2)
        nw["CTR(%)"] = (nw["clicks"] / nw["impressions"] * 100).fillna(0).round(2)
        nw["花費($)"] = nw["spend"].apply(lambda x: f"${x:,.0f}")
        nw["安裝"] = nw["installs"].apply(lambda x: f"{int(x):,}")
        st.dataframe(nw[["network", "花費($)", "安裝", "CPI($)", "CTR(%)"]],
                     hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("📦 Ad Group 排行 ─ 依花費")
    if "ad_group" in df.columns:
        ag = df.groupby("ad_group").agg(
            spend=("spend", "sum"),
            installs=("installs", "sum"),
            clicks=("clicks", "sum"),
        ).reset_index()
        ag["CPI($)"] = (ag["spend"] / ag["installs"]).replace(
            [float("inf"), float("-inf")], 0).fillna(0).round(2)
        ag = ag.sort_values("spend", ascending=False).head(20)
        ag["花費($)"] = ag["spend"].apply(lambda x: f"${x:,.0f}")
        ag["安裝"] = ag["installs"].apply(lambda x: f"{int(x):,}")
        st.dataframe(ag[["ad_group", "花費($)", "安裝", "CPI($)"]],
                     hide_index=True, use_container_width=True, height=460)


# ──────────────────────────────────────────────────────────────────────
#  主程式
# ──────────────────────────────────────────────────────────────────────
df_raw = load_unified()
if df_raw is None or df_raw.empty:
    st.error("無法載入資料,請檢查 Google Sheet 連線設定。")
    st.stop()

with st.sidebar:
    st.markdown("### 🎰 Ocean Fishooter")

    # 資料新鮮度
    min_date = df_raw["date"].min()
    max_date = df_raw["date"].max()
    days_behind = (datetime.now().date() - max_date.date()).days
    if days_behind <= 1:
        icon, txt, bg, border = "🟢", "正常", "#0F3A1F", "#16A34A"
    elif days_behind <= 3:
        icon, txt, bg, border = "🟡", "稍舊", "#3F2A0E", "#D97706"
    else:
        icon, txt, bg, border = "🔴", "過期", "#3F1212", "#DC2626"
    st.markdown(
        f"""<div style="background:{bg};padding:10px 12px;border-radius:8px;
        border-left:3px solid {border};margin-bottom:14px">
        <div style="font-size:11.5px;color:#94A3B8;margin-bottom:2px">資料狀態</div>
        <div style="font-size:14px;font-weight:600;color:#F8FAFC">
        📅 最新:{max_date.strftime('%Y-%m-%d')}</div>
        <div style="font-size:12px;color:#CBD5E1;margin-top:2px">
        {icon} 距今 {days_behind} 天({txt})</div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.title("篩選條件")
    default_end = max_date.date()
    default_start = default_end.replace(day=1)
    if default_start < min_date.date():
        default_start = min_date.date()
    date_range = st.date_input(
        "日期範圍",
        value=(default_start, default_end),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )

    # ── 國家篩選 ──
    all_country = sorted(df_raw["country"].dropna().unique().tolist())
    country_choice = st.radio(
        "🌍 國家", ["全部"] + all_country, horizontal=True, index=0,
    )

    # ── 媒體篩選 ──
    all_media = sorted(df_raw["media"].dropna().unique().tolist())
    media_choice = st.radio(
        "📱 媒體", ["全部"] + all_media, horizontal=True, index=0,
    )

    # ── OS 篩選(把雜訊值歸成「其他」)──
    def _norm_os(s):
        s = str(s).strip().upper()
        if s in ("IOS", "I"):
            return "iOS"
        if s in ("AND", "ANDROID"):
            return "Android"
        return "其他"

    df_raw["_os_group"] = df_raw["os"].apply(_norm_os)
    os_choice = st.radio(
        "📱 OS", ["全部", "iOS", "Android", "其他"], horizontal=True, index=0,
    )

    st.markdown("---")
    if len(date_range) == 2:
        _len = (date_range[1] - date_range[0]).days + 1
        _prev_end = date_range[0] - pd.Timedelta(days=1)
        _prev_start = _prev_end - pd.Timedelta(days=_len - 1)
        st.caption(
            f"**對比期**:{_prev_start.strftime('%Y-%m-%d')} ~ "
            f"{_prev_end.strftime('%Y-%m-%d')}"
        )
        st.caption(f"(同長度 {_len} 天)")
    st.markdown("---")
    st.caption(f"資料範圍:{min_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')}")
    st.caption(f"頁面開啟時間:{datetime.now().strftime('%Y/%m/%d %H:%M')}")
    if st.button("🔄 重新載入資料", help="清除快取並從 Google Sheet 重新拉資料"):
        st.cache_data.clear()
        st.rerun()

# 套用篩選
df = df_raw.copy()
df_prev = pd.DataFrame()
if len(date_range) == 2:
    start, end = date_range[0], date_range[1]
    df = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]
    period_len = (end - start).days + 1
    prev_end = start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=period_len - 1)
    df_prev = df_raw[(df_raw["date"].dt.date >= prev_start)
                     & (df_raw["date"].dt.date <= prev_end)]

if os_choice != "全部":
    df = df[df["_os_group"] == os_choice]
    df_prev = df_prev[df_prev["_os_group"] == os_choice] if not df_prev.empty else df_prev
if country_choice != "全部":
    df = df[df["country"] == country_choice]
    df_prev = df_prev[df_prev["country"] == country_choice] if not df_prev.empty else df_prev
if media_choice != "全部":
    df = df[df["media"] == media_choice]
    df_prev = df_prev[df_prev["media"] == media_choice] if not df_prev.empty else df_prev

st.title("🌊 Ocean Fishooter 廣告儀表板")
st.caption(
    f"UA 投放 | 媒體:{media_choice} × 國家:{country_choice} × OS:{os_choice}"
)
st.markdown("---")

tab1, tab2 = st.tabs([
    "🎯 投放總覽",
    "🔍 媒體深度",
])

with tab1:
    show_kpis(df, df_prev)
    st.markdown("---")
    st.subheader("📈 每日趨勢(花費 / 安裝 / CPI)")
    show_daily_trend(df)
    st.markdown("---")
    st.subheader("🥧 媒體分布")
    show_media_mix(df)
    st.markdown("---")
    st.subheader("⚠️ 異常警示")
    show_alerts(df, df_prev)

with tab2:
    deep_media = st.radio(
        "選擇媒體",
        ["Meta", "ASA", "Google", "TikTok", "Applovin", "Moloco"],
        horizontal=True, key="deep_tab",
    )

    if deep_media == "Meta":
        # Meta 用三層 drill-down(Campaign → Ad Group → Ad)
        if len(date_range) == 2:
            deep_dive_meta(date_range[0], date_range[1])
        else:
            st.warning("請選擇完整日期範圍")
    else:
        # 其他媒體:先顯示 Campaign 排行
        st.subheader(f"🎬 {deep_media} Campaign 排行")
        show_campaign_table(df, deep_media)

        # ASA / Google 還有獨家深度
        if len(date_range) == 2:
            if deep_media == "ASA":
                st.markdown("---")
                deep_dive_asa(date_range[0], date_range[1])
            elif deep_media == "Google":
                st.markdown("---")
                deep_dive_google(date_range[0], date_range[1])
        # TikTok / Applovin / Moloco 沒有獨家欄位,只看 campaign
