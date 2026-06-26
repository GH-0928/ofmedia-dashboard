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


def _meta_ad_detail_chart(sub: pd.DataFrame, ad_name: str,
                            start_date, end_date) -> None:
    """素材層 ── 顯示某個素材的 14 天詳細走勢:CPI / 花費 / 安裝 三軸。"""
    ad_df = sub[sub["ad"] == ad_name].copy()
    ad_df["date_only"] = ad_df["date"].dt.normalize()
    daily = ad_df.groupby("date_only").agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
    ).reset_index()

    # 填滿 7 天空白日期
    date_range = pd.date_range(start=start_date, end=end_date.normalize(), freq="D")
    full = pd.DataFrame({"date_only": date_range})
    full = full.merge(daily, on="date_only", how="left").fillna(0)
    full["cpi"] = full.apply(
        lambda r: round(r["spend"] / r["installs"], 2) if r["installs"] > 0 else 0,
        axis=1,
    )

    # 配色:CPI 跟上方 sparkline 同色(藍),安裝綠色(正向結果),花費琥珀色背景柱
    COLOR_CPI = "#3B82F6"      # 亮藍,跟 sparkline 一致
    COLOR_INSTALLS = "#10B981"  # 翠綠,正面結果
    COLOR_SPEND = "#F59E0B"     # 琥珀,暖色背景

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=full["date_only"], y=full["spend"], name="花費",
        marker_color=COLOR_SPEND, opacity=0.22, yaxis="y1",
        hovertemplate="💰 $%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=full["date_only"], y=full["installs"], name="安裝",
        mode="lines+markers", line=dict(color=COLOR_INSTALLS, width=2.2),
        marker=dict(size=7), yaxis="y2",
        hovertemplate="📲 %{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=full["date_only"], y=full["cpi"], name="CPI",
        mode="lines+markers", line=dict(color=COLOR_CPI, width=3),
        marker=dict(size=8), yaxis="y3",
        hovertemplate="💎 $%{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=380, hovermode="x unified",
        margin=dict(t=30, b=20, l=10, r=80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor="#334155", domain=[0, 0.92],
                   tickformat="%m/%d", type="date"),
        yaxis=dict(title=dict(text="花費 ($)", font=dict(color=COLOR_SPEND)),
                   showgrid=True, gridcolor="#334155",
                   tickfont=dict(color=COLOR_SPEND)),
        yaxis2=dict(title=dict(text="安裝", font=dict(color=COLOR_INSTALLS)),
                    overlaying="y", side="right", showgrid=False,
                    position=0.92, tickfont=dict(color=COLOR_INSTALLS)),
        yaxis3=dict(title=dict(text="CPI ($)", font=dict(color=COLOR_CPI)),
                    overlaying="y", side="right", showgrid=False,
                    anchor="free", position=1.0,
                    tickfont=dict(color=COLOR_CPI)),
    )
    st.plotly_chart(fig, use_container_width=True)


def _add_cpi_trend_cols(stats: pd.DataFrame, raw_sub: pd.DataFrame,
                         group_col: str) -> pd.DataFrame:
    """為 stats DataFrame 加上 14 天 sparkline + 昨日/3日/7日 CPI 四欄。

    沒安裝那天的單日 CPI = 0;3日/7日 CPI 用累積花費 / 累積安裝(不是平均)。
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

    sparkline_map, yday_map, d3_map, d7_map = {}, {}, {}, {}
    for key in stats[group_col].unique():
        ad_daily = daily[daily[group_col] == key].set_index("date_only")
        # 14 天 sparkline
        cpi_values = []
        for d in date_range_14d:
            if d in ad_daily.index:
                sp = ad_daily.loc[d, "spend"]
                inst = ad_daily.loc[d, "installs"]
                cpi_values.append(round(sp / inst, 2) if inst > 0 else 0.0)
            else:
                cpi_values.append(0.0)
        sparkline_map[key] = cpi_values
        # 昨日(最新一天)
        if max_d_norm in ad_daily.index:
            sp = ad_daily.loc[max_d_norm, "spend"]
            inst = ad_daily.loc[max_d_norm, "installs"]
            yday_map[key] = round(sp / inst, 2) if inst > 0 else 0.0
        else:
            yday_map[key] = 0.0
        # 3 日累積
        d3_data = ad_daily.loc[ad_daily.index >= max_d_norm - pd.Timedelta(days=2)]
        sp3, inst3 = d3_data["spend"].sum(), d3_data["installs"].sum()
        d3_map[key] = round(sp3 / inst3, 2) if inst3 > 0 else 0.0
        # 7 日累積
        d7_data = ad_daily.loc[ad_daily.index >= max_d_norm - pd.Timedelta(days=6)]
        sp7, inst7 = d7_data["spend"].sum(), d7_data["installs"].sum()
        d7_map[key] = round(sp7 / inst7, 2) if inst7 > 0 else 0.0

    stats = stats.copy()
    stats["CPI 走勢"] = stats[group_col].map(sparkline_map)
    stats["昨日CPI"] = stats[group_col].map(yday_map)
    stats["3日CPI"] = stats[group_col].map(d3_map)
    stats["7日CPI"] = stats[group_col].map(d7_map)
    return stats


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
    """顯示帶選取的 dataframe,回傳被點擊的列索引(-1 = 沒選)。

    若 stats 含 CPI 走勢 / 昨日CPI / 3日CPI / 7日CPI 欄,會自動加進顯示。
    """
    has_trend = "CPI 走勢" in stats.columns
    base_cols = [key_col, "spend", "installs", "CPI($)", "CTR(%)", "CVR(%)", "CPM($)"]
    base_labels = [label, "花費($)", "安裝", "CPI($)", "CTR(%)", "CVR(%)", "CPM($)"]

    if has_trend:
        extra_cols = ["昨日CPI", "3日CPI", "7日CPI", "CPI 走勢"]
        extra_labels = ["昨日CPI($)", "3日CPI($)", "7日CPI($)", "CPI 走勢(14天)"]
    else:
        extra_cols, extra_labels = [], []

    disp = stats[base_cols + extra_cols].copy()
    disp.columns = base_labels + extra_labels
    disp["花費($)"] = disp["花費($)"].apply(lambda x: f"${x:,.0f}")
    disp["安裝"] = disp["安裝"].apply(lambda x: f"{int(x):,}")

    column_config = {}
    if has_trend:
        column_config = {
            "昨日CPI($)": st.column_config.NumberColumn(
                "昨日CPI($)", help="最新一天的 CPI", format="$%.2f"),
            "3日CPI($)": st.column_config.NumberColumn(
                "3日CPI($)", help="最近 3 天累積花費 / 累積安裝", format="$%.2f"),
            "7日CPI($)": st.column_config.NumberColumn(
                "7日CPI($)", help="最近 7 天累積花費 / 累積安裝", format="$%.2f"),
            "CPI 走勢(14天)": st.column_config.LineChartColumn(
                "CPI 走勢(14天)", help="最近 14 天 CPI 變化(沒安裝那天 = 0)", y_min=0),
        }

    event = st.dataframe(
        disp,
        hide_index=True,
        use_container_width=True,
        height=460,
        on_select="rerun",
        selection_mode="single-row",
        key=table_key,
        column_config=column_config,
    )
    if event and getattr(event, "selection", None):
        rows = event.selection.get("rows", [])
        if rows:
            return rows[0]
    return -1


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


def deep_dive_meta(date_start, date_end, os_choice="全部", country_choice="全部") -> None:
    df = load_meta_raw()
    if df.empty:
        st.info("Meta_raw 無資料")
        return
    df = df[(df["date"].dt.date >= date_start) & (df["date"].dt.date <= date_end)]
    df = _apply_raw_filters(df, os_choice, country_choice)
    if df.empty:
        st.info("此期間 Meta 無資料(可能受篩選影響)")
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
    if ss.meta_drill_ad_group:
        # 在素材層:給兩個返回選項
        c1, c2, _ = st.columns([1.5, 1.8, 4])
        with c1:
            if st.button("← 返回 Ad Group", key="back_ag"):
                ss.meta_drill_ad_group = None
                st.rerun()
        with c2:
            if st.button("↩ 回到 Campaign 清單", key="back_to_cmp"):
                ss.meta_drill_campaign = None
                ss.meta_drill_ad_group = None
                st.rerun()
    elif ss.meta_drill_campaign:
        c1, _ = st.columns([1.5, 5])
        with c1:
            if st.button("← 返回 Campaign", key="back_cmp"):
                ss.meta_drill_campaign = None
                st.rerun()

    # ── 第 1 層:Campaign ──
    if ss.meta_drill_campaign is None:
        st.caption("👇 **點任一列查看該 Campaign 的 Ad Group**")
        stats = _meta_metrics(df, "campaign")
        stats = _add_cpi_trend_cols(stats, df, "campaign")
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
        stats = _add_cpi_trend_cols(stats, sub, "ad_group")
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
        # 加狀態欄(各素材最新一筆的 status)
        status_map = _latest_status_map(sub, "ad")
        stats["狀態"] = stats["ad"].map(lambda x: _status_zh(status_map.get(x, "")))

        # 加 14 天 sparkline + 昨日/3日/7日 CPI
        stats = _add_cpi_trend_cols(stats, sub, "ad")

        # 計算用變數(給後續詳細圖)
        max_d = sub["date"].max()
        start_14d = (max_d - pd.Timedelta(days=13)).normalize()

        st.caption("👇 **點任一列查看該素材 14 天 CPI / 花費 / 安裝 趨勢圖**")
        disp = stats[["狀態", "ad", "spend", "installs", "CPI($)",
                       "CTR(%)", "CVR(%)", "CPM($)",
                       "昨日CPI", "3日CPI", "7日CPI", "CPI 走勢"]].copy()
        disp.columns = ["狀態", "素材(Ad)", "花費($)", "安裝", "CPI($)",
                         "CTR(%)", "CVR(%)", "CPM($)",
                         "昨日CPI($)", "3日CPI($)", "7日CPI($)", "CPI 走勢(14天)"]
        disp["花費($)"] = disp["花費($)"].apply(lambda x: f"${x:,.0f}")
        disp["安裝"] = disp["安裝"].apply(lambda x: f"{int(x):,}")

        event = st.dataframe(
            disp,
            hide_index=True,
            use_container_width=True,
            height=460,
            on_select="rerun",
            selection_mode="single-row",
            key="tbl_meta_ad",
            column_config={
                "昨日CPI($)": st.column_config.NumberColumn(
                    "昨日CPI($)",
                    help="最新一天的 CPI",
                    format="$%.2f",
                ),
                "3日CPI($)": st.column_config.NumberColumn(
                    "3日CPI($)",
                    help="最近 3 天累積花費 / 累積安裝",
                    format="$%.2f",
                ),
                "7日CPI($)": st.column_config.NumberColumn(
                    "7日CPI($)",
                    help="最近 7 天累積花費 / 累積安裝",
                    format="$%.2f",
                ),
                "CPI 走勢(14天)": st.column_config.LineChartColumn(
                    "CPI 走勢(14天)",
                    help="最近 14 天 CPI 變化(沒安裝那天 = 0)",
                    y_min=0,
                ),
            },
        )

        # 點選列 → 顯示該素材詳細時序圖
        selected_ad = None
        if event and getattr(event, "selection", None):
            rows = event.selection.get("rows", [])
            if rows:
                selected_ad = stats.iloc[rows[0]]["ad"]

        if selected_ad:
            st.markdown("---")
            st.subheader(f"📈 {selected_ad}  ── 14 天詳細走勢")
            _meta_ad_detail_chart(sub, selected_ad, start_14d, max_d)


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
    df = load_asa_raw()
    if df.empty:
        st.info("ASA_raw 無資料")
        return
    df = df[(df["date"].dt.date >= date_start) & (df["date"].dt.date <= date_end)]
    df = _apply_raw_filters(df, os_choice, country_choice)
    if df.empty:
        st.info("此期間 ASA 無資料(可能受篩選影響)")
        return

    # ── 篩選器:Campaign + Match Type ──
    c1, c2 = st.columns([2, 1])
    with c1:
        campaign_opts = ["全部 Campaign"] + sorted(df["campaign"].unique().tolist())
        sel_cmp = st.selectbox("📁 Campaign", campaign_opts, key="asa_cmp_filter")
    with c2:
        if "match_type" in df.columns:
            mt_raw = sorted(df["match_type"].dropna().unique().tolist())
            mt_opts = ["全部"] + [_match_type_zh(m) for m in mt_raw]
            mt_label_to_raw = {_match_type_zh(m): m for m in mt_raw}
            sel_mt = st.radio(
                "🎯 Match Type", mt_opts, horizontal=True, key="asa_mt_filter",
            )
        else:
            sel_mt = "全部"

    # 套用篩選
    df_f = df.copy()
    if sel_cmp != "全部 Campaign":
        df_f = df_f[df_f["campaign"] == sel_cmp]
    if sel_mt != "全部" and "match_type" in df_f.columns:
        df_f = df_f[df_f["match_type"] == mt_label_to_raw.get(sel_mt, sel_mt)]

    if df_f.empty:
        st.warning("篩選後無資料")
        return

    st.markdown("---")
    st.subheader("🔑 關鍵字(Keyword)排行 ─ 依花費")
    if "keyword" in df_f.columns:
        kw = df_f.groupby("keyword").agg(
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
    st.subheader("🔎 Search Term 表現 ─ 依花費")
    if "search_term" in df_f.columns:
        st_df = df_f.groupby("search_term").agg(
            spend=("spend", "sum"),
            installs=("installs", "sum"),
        ).reset_index()
        st_df = st_df[st_df["spend"] > 0].sort_values("spend", ascending=False).head(30)
        st_df["CPI($)"] = (st_df["spend"] / st_df["installs"]).replace(
            [float("inf"), float("-inf")], 0).fillna(0).round(2)
        st_df["花費($)"] = st_df["spend"].apply(lambda x: f"${x:,.0f}")
        st_df["安裝"] = st_df["installs"].apply(lambda x: f"{int(x):,}")
        st.dataframe(st_df[["search_term", "花費($)", "安裝", "CPI($)"]],
                     hide_index=True, use_container_width=True)


def _google_table(df: pd.DataFrame, group_col: str, label: str,
                   sort_by_spend: bool = True, head: int = None) -> None:
    """產出 Google 深度頁的標準表格(8 欄,CPI 紅色粗體突顯)。"""
    g = df.groupby(group_col).agg(
        spend=("spend", "sum"),
        installs=("installs", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
    ).reset_index()
    g["CPM"] = (g["spend"] / g["impressions"] * 1000).replace(
        [float("inf"), float("-inf")], 0).fillna(0)
    g["CTR"] = (g["clicks"] / g["impressions"] * 100).replace(
        [float("inf"), float("-inf")], 0).fillna(0)
    g["CPI"] = (g["spend"] / g["installs"]).replace(
        [float("inf"), float("-inf")], 0).fillna(0)
    g["CVR"] = (g["installs"] / g["clicks"] * 100).replace(
        [float("inf"), float("-inf")], 0).fillna(0)
    if sort_by_spend:
        g = g.sort_values("spend", ascending=False)
    if head:
        g = g.head(head)
    if g.empty:
        st.info("無資料")
        return

    # 預先把所有數字格式化成字串(避免 Styler.format 觸發額外依賴)
    disp = pd.DataFrame({
        label: g[group_col].values,
        "花費($)": [f"${x:,.0f}" for x in g["spend"]],
        "曝光": [f"{int(x):,}" for x in g["impressions"]],
        "CPM($)": [f"${x:.2f}" for x in g["CPM"]],
        "點擊": [f"{int(x):,}" for x in g["clicks"]],
        "CTR(%)": [f"{x:.2f}%" for x in g["CTR"]],
        "安裝": [f"{int(x):,}" for x in g["installs"]],
        "CPI($)": [f"${x:.2f}" for x in g["CPI"]],
        "CVR(%)": [f"{x:.2f}%" for x in g["CVR"]],
    })

    # CPI 欄紅色粗體(只用 set_properties,不需要 matplotlib)
    styled = disp.style.set_properties(
        subset=["CPI($)"],
        **{"color": "#EF4444", "font-weight": "700"},
    )
    st.dataframe(styled, hide_index=True, use_container_width=True, height=460)


def deep_dive_google(date_start, date_end, os_choice="全部", country_choice="全部") -> None:
    df = load_google_raw()
    if df.empty:
        st.info("Google_raw 無資料")
        return
    df = df[(df["date"].dt.date >= date_start) & (df["date"].dt.date <= date_end)]
    df = _apply_raw_filters(df, os_choice, country_choice)
    if df.empty:
        st.info("此期間 Google 無資料(可能受篩選影響)")
        return

    st.subheader("🌐 Network 表現對比(搜尋 / 多媒體聯播網 / YouTube / 搜尋夥伴)")
    if "network" in df.columns:
        _google_table(df, "network", "Network")

    st.markdown("---")
    st.subheader("📦 Ad Group 排行 ─ 依花費")
    if "ad_group" in df.columns:
        _google_table(df, "ad_group", "Ad Group", head=30)


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
            deep_dive_meta(date_range[0], date_range[1], os_choice, country_choice)
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
                deep_dive_asa(date_range[0], date_range[1], os_choice, country_choice)
            elif deep_media == "Google":
                st.markdown("---")
                deep_dive_google(date_range[0], date_range[1], os_choice, country_choice)
        # TikTok / Applovin / Moloco 沒有獨家欄位,只看 campaign
