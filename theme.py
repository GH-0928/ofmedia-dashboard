# -*- coding: utf-8 -*-
"""視覺系統 ── OFmedia 廣告儀表板。

這個模組是全站樣式的**唯一來源**：色階、間距、字級、圓角、圖表主題、
共用 HTML 元件都集中在這裡。表格本身由 grid.py 負責。

規則：app.py / auth.py / calendar_view.py 不再自己寫 hex 色碼，一律引用
這裡的 token。要調整整站外觀時只改這個檔案。

設計取向（依使用情境決定）：桌機、每天盯投放。
  - 資訊密度優先：間距收緊、卡片扁平、不做裝飾性動畫
  - 數字可比對：全站數字用 tabular-nums（等寬數字），上下行對得齊
  - 層級靠排版：字級 / 字重 / 顏色深淺，不靠 emoji
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════
#  1. 設計 token
# ══════════════════════════════════════════════════════════════════════

# ── 色階：深色介面的六層背景，由深到淺 ──────────────────────────────
# BG 必須與 .streamlit/config.toml 的 backgroundColor 一致，否則卡片與
# 頁面背景會對不起來。
BG          = "#0E1117"   # 頁面底色
SURFACE     = "#141B26"   # 卡片 / 容器
SURFACE_2   = "#1A2230"   # 卡片內的次層（表頭、hover）
BORDER      = "#222C3C"   # 一般邊框、分隔線
BORDER_HI   = "#2F3B4F"   # 強調邊框（hover / 選中）

# ── 文字三層 ──────────────────────────────────────────────────────
TEXT        = "#E6EDF7"   # 主要文字、數值
TEXT_MID    = "#9AA8BC"   # 標籤、說明
TEXT_DIM    = "#64748B"   # 註腳、次要資訊

# ── 語意色 ────────────────────────────────────────────────────────
ACCENT      = "#3B82F6"   # 主色（選中、連結、主要按鈕）
ACCENT_HI   = "#60A5FA"   # 主色亮版（圖表線條、hover）
POS         = "#34D399"   # 正向（成本下降、量成長）
NEG         = "#F87171"   # 負向（成本上升、量下滑）
WARN        = "#FBBF24"   # 注意（需要看一眼，但不一定是壞事）

# 警示區塊的底色：用極低飽和的同色系，避免大面積色塊搶走數字的注意力
POS_BG      = "#10231B"
NEG_BG      = "#2A1416"
WARN_BG     = "#2A2110"

# ── 媒體配色：深色底下高對比、六個色相拉開 ─────────────────────────
# 以辨識度為準，不用品牌色（Meta 藍與 Google 藍在深色底下會分不出來）。
MEDIA_COLORS = {
    "Meta":     "#4F8EF7",   # 亮藍
    "Google":   "#34D399",   # 翠綠
    "ASA":      "#CBD5E1",   # 亮灰（Apple 中性）
    "TikTok":   "#F472B6",   # 粉紅
    "Applovin": "#FB923C",   # 橘
    "Moloco":   "#A78BFA",   # 紫
}

# 指標專屬色：漏斗與流量成本在多張圖之間要維持同一個顏色語意
CTR_C       = "#22D3EE"   # CTR（素材吸引力）
CVR_C       = "#A78BFA"   # CVR（點擊後轉化）
CPM_C       = "#FB923C"   # CPM（流量成本）
ACCENT_DEEP = "#1E3A8A"   # 主色深版（品牌小標記的漸層尾端）

# 圖表通用色序（媒體以外的類別型資料用這組，與媒體色同一套色相邏輯）
CHART_SEQ = ["#4F8EF7", "#34D399", "#FBBF24", "#F472B6", "#A78BFA",
             "#22D3EE", "#FB923C", "#CBD5E1"]

# ── 間距 / 圓角 / 字級 ────────────────────────────────────────────
R_SM, R_MD, R_LG = "6px", "9px", "12px"           # 圓角
FS_LABEL, FS_BODY = "11.5px", "13px"
# KPI 數值：視窗窄時自動縮小，配合 nowrap 保證一行放得下
FS_VALUE = "clamp(17px, 1.5vw, 25px)"

# sidebar 寬度：預設 300px 放不下「近 14 天」這種四字選項的分段控制項
SIDEBAR_W = "330px"

# Plotly 圖表的統一高度（避免每張圖各寫各的）
H_MAIN, H_SUB, H_MINI = 340, 230, 180

# Plotly 工具列預設關掉：hover 時冒出一排相機 / 縮放圖示，是「未完成的
# 內嵌圖表」最明顯的痕跡，而盯投放時那排按鈕幾乎不會用到。
PLOTLY_CONFIG = {"displayModeBar": False, "scrollZoom": False}


# ══════════════════════════════════════════════════════════════════════
#  2. 全域 CSS
# ══════════════════════════════════════════════════════════════════════
def inject_css() -> str:
    """回傳全站 CSS（呼叫端用 st.markdown(..., unsafe_allow_html=True)）。"""
    return f"""
<style>
/* ── Streamlit 預設裝飾 ──────────────────────────────────────────
   不要整個藏 [data-testid="stToolbar"]。Streamlit 1.55 把「展開 sidebar」
   的按鈕（stExpandSidebarButton）也塞在 toolbar 裡，整個 display:none 會
   讓它變成 0x0 —— sidebar 一旦被收合就再也打不開，而收合狀態還會被記在
   瀏覽器 localStorage（stSidebarCollapsed-<網址>），跨分頁、跨天都記得，
   initial_sidebar_state="expanded" 也蓋不掉。只藏 Deploy 與主選單那組。 */
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden; height: 0;}}
header[data-testid="stHeader"] {{background: transparent; height: 0;}}
[data-testid="stToolbarActions"] {{display: none;}}
[data-testid="stAppDeployButton"] {{display: none;}}
[data-testid="stMainMenu"] {{display: none;}}
[data-testid="stDecoration"] {{display: none;}}
[data-testid="stStatusWidget"] {{display: none;}}

/* ── 版面 ─────────────────────────────────────────────────────── */
.block-container {{
    padding-top: 1.6rem !important;
    padding-bottom: 3rem !important;
    max-width: 1560px;
}}

/* 全站等寬數字：KPI、表格、圖表座標軸的位數對得齊，掃視時不用重新對焦 */
html, body, [class*="css"], .stMarkdown, [data-testid="stMetricValue"] {{
    font-feature-settings: "tnum" 1, "cv01" 1;
}}

h1, h2, h3 {{letter-spacing: -0.4px;}}
h1 {{font-weight: 700 !important;}}

/* ── 頂部檢視列 ───────────────────────────────────────────────── */
.of-topbar {{
    display: flex; align-items: center; gap: 14px;
    padding: 12px 18px; margin-bottom: 18px;
    background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: {R_LG};
}}
.of-topbar-title {{
    font-size: 16px; font-weight: 700; color: {TEXT};
    letter-spacing: -0.3px; white-space: nowrap;
}}
.of-topbar-sub {{font-size: {FS_LABEL}; color: {TEXT_DIM}; margin-top: 2px;}}
.of-topbar-spacer {{flex: 1;}}
.of-chips {{display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end;}}
.of-chip {{
    display: inline-flex; align-items: center; gap: 5px;
    padding: 4px 10px; border-radius: 999px;
    background: {SURFACE_2}; border: 1px solid {BORDER};
    font-size: {FS_LABEL}; color: {TEXT_MID}; white-space: nowrap;
}}
.of-chip b {{color: {TEXT}; font-weight: 600;}}
.of-chip-on {{border-color: {ACCENT}; background: rgba(59,130,246,0.12);}}

/* ── 區塊標題：小標籤 + 延伸細線，取代 subheader + 水平線 ───────── */
.of-sec {{
    display: flex; align-items: baseline; gap: 10px;
    margin: 22px 0 10px;
}}
.of-sec-t {{
    font-size: 13px; font-weight: 700; color: {TEXT};
    letter-spacing: 0.2px; white-space: nowrap;
}}
.of-sec-d {{font-size: {FS_LABEL}; color: {TEXT_DIM}; white-space: nowrap;}}
.of-sec-line {{flex: 1; height: 1px; background: {BORDER};}}

/* ── KPI 卡 ───────────────────────────────────────────────────── */
.of-kpi {{
    position: relative;
    display: flex; align-items: center; gap: 10px;
    background: {SURFACE}; border: 1px solid {BORDER};
    border-left: 2px solid {BORDER_HI};
    border-radius: {R_MD}; padding: 11px 14px 11px 13px;
    min-height: 78px; transition: border-color .12s ease;
}}
.of-kpi:hover {{border-color: {BORDER_HI};}}
.of-kpi-vol  {{border-left-color: {ACCENT};}}
.of-kpi-rate {{border-left-color: {WARN};}}
.of-kpi-body {{flex: 1; min-width: 0;}}
.of-kpi-label {{
    font-size: {FS_LABEL}; font-weight: 600; color: {TEXT_MID};
    letter-spacing: .3px; margin-bottom: 3px;
}}
.of-kpi-value {{
    font-size: {FS_VALUE}; font-weight: 700; color: {TEXT};
    line-height: 1.05; letter-spacing: -0.8px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.of-kpi-delta {{
    font-size: {FS_LABEL}; margin-top: 4px; font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
/* 視窗再窄下去，四張卡各自不到 260px，這時走勢線讓位給數字 */
@media (max-width: 1150px) {{
    .of-kpi svg {{display: none;}}
}}
.of-kpi-flat {{color: {TEXT_DIM}; font-weight: 500;}}
.of-good {{color: {POS};}}
.of-bad  {{color: {NEG};}}

/* ── 警示列 ───────────────────────────────────────────────────── */
.of-alert {{
    display: flex; align-items: flex-start; gap: 9px;
    padding: 9px 13px; margin-bottom: 6px;
    border-radius: {R_SM}; border: 1px solid transparent;
    border-left-width: 3px; font-size: {FS_BODY}; color: {TEXT};
    line-height: 1.5;
}}
.of-alert-tag {{
    font-weight: 700; font-size: {FS_LABEL}; letter-spacing: .3px;
    padding-top: 1px; white-space: nowrap;
}}
.of-alert-warn {{background: {WARN_BG}; border-left-color: {WARN};}}
.of-alert-warn .of-alert-tag {{color: {WARN};}}
.of-alert-neg  {{background: {NEG_BG}; border-left-color: {NEG};}}
.of-alert-neg .of-alert-tag {{color: {NEG};}}
.of-alert-pos  {{background: {POS_BG}; border-left-color: {POS};}}
.of-alert-pos .of-alert-tag {{color: {POS};}}

/* ── 麵包屑（Meta 三層下鑽）───────────────────────────────────── */
.of-crumb {{
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    padding: 7px 12px; margin-bottom: 10px;
    background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: {R_SM}; font-size: {FS_BODY}; color: {TEXT_MID};
}}
.of-crumb-on {{color: {TEXT}; font-weight: 600;}}
.of-crumb-sep {{color: {TEXT_DIM};}}

/* ── 操作紀錄列 ───────────────────────────────────────────────── */
.of-op {{
    display: flex; align-items: baseline; gap: 9px;
    padding: 5px 0; border-bottom: 1px solid {BORDER};
    font-size: 12.5px; color: {TEXT};
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.of-op:last-child {{border-bottom: none;}}
.of-op-date {{color: {TEXT_DIM}; font-size: {FS_LABEL}; white-space: nowrap;}}
.of-op-type {{color: {ACCENT_HI}; font-weight: 600;}}
.of-op-note {{color: {TEXT_MID};}}

/* ── 資料狀態卡（sidebar）─────────────────────────────────────── */
.of-status {{
    padding: 9px 11px; border-radius: {R_SM};
    border: 1px solid {BORDER}; border-left-width: 3px;
    margin-bottom: 10px;
}}
.of-status-l {{font-size: 10.5px; color: {TEXT_DIM}; letter-spacing: .4px;}}
.of-status-v {{font-size: {FS_BODY}; font-weight: 700; color: {TEXT}; margin-top: 2px;}}
.of-status-s {{font-size: {FS_LABEL}; margin-top: 3px;}}

/* ── Streamlit 元件微調 ───────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{gap: 2px; border-bottom: 1px solid {BORDER};}}
.stTabs [data-baseweb="tab"] {{
    border-radius: {R_SM} {R_SM} 0 0; padding: 8px 16px;
    font-size: {FS_BODY}; font-weight: 600; color: {TEXT_MID};
}}
.stTabs [data-baseweb="tab"]:hover {{background: {SURFACE_2}; color: {TEXT};}}
.stTabs [aria-selected="true"] {{background: {SURFACE}; color: {TEXT} !important;}}

.stButton button, .stDownloadButton button {{
    border-radius: {R_SM}; font-weight: 600; font-size: {FS_BODY};
    border: 1px solid {BORDER}; transition: border-color .12s ease;
}}
.stButton button:hover, .stDownloadButton button:hover {{
    border-color: {ACCENT}; color: {TEXT};
}}

[data-testid="stDataFrame"] {{
    border-radius: {R_MD}; overflow: hidden; border: 1px solid {BORDER};
}}
[data-testid="stExpander"] {{
    border-radius: {R_MD}; border: 1px solid {BORDER}; background: {SURFACE};
}}
[data-testid="stExpander"] summary {{font-size: {FS_BODY}; color: {TEXT_MID};}}

[data-testid="stSidebar"] {{
    background: {BG}; border-right: 1px solid {BORDER};
    width: {SIDEBAR_W} !important; min-width: {SIDEBAR_W} !important;
}}
/* 收合時 Streamlit 位移的距離是寫死的預設寬度（300px），加寬 sidebar 後
   若不同步改這個位移，收起來會有一條沒縮進去、蓋在內容上。 */
[data-testid="stSidebar"][aria-expanded="false"] {{
    transform: translateX(-{SIDEBAR_W}) !important;
}}
/* 分段控制項（期間 / 媒體 / OS）選項多時換行，不要橫向溢出 sidebar */
[data-testid="stSegmentedControl"] > div,
[data-testid="stButtonGroup"] > div,
[data-baseweb="button-group"] {{flex-wrap: wrap; gap: 3px;}}
[data-testid="stSidebar"] [data-testid="stSegmentedControl"] button,
[data-testid="stSidebar"] [data-testid="stButtonGroup"] button {{
    font-size: 12px; padding: 2px 10px;
}}
[data-testid="stSidebar"] .block-container {{padding-top: 1.2rem;}}
[data-testid="stSidebar"] hr {{margin: .9rem 0; border-color: {BORDER};}}
/* sidebar 內的標籤字級收小，讓四組篩選塞得下又不擁擠 */
[data-testid="stSidebar"] label p {{font-size: 12px !important; color: {TEXT_MID};}}

hr {{border-color: {BORDER} !important; margin: .9rem 0;}}
a {{color: {ACCENT_HI} !important;}}

::-webkit-scrollbar {{width: 9px; height: 9px;}}
::-webkit-scrollbar-track {{background: transparent;}}
::-webkit-scrollbar-thumb {{background: {BORDER_HI}; border-radius: 5px;}}
::-webkit-scrollbar-thumb:hover {{background: {TEXT_DIM};}}
</style>
"""


# ══════════════════════════════════════════════════════════════════════
#  3. 圖表主題
# ══════════════════════════════════════════════════════════════════════
def style_fig(fig, height: int = H_MAIN, legend: bool = True,
              margin: dict | None = None, title: str | None = None,
              title_color: str | None = None):
    """套用統一的 Plotly 主題。所有圖表都要經過這個函式。

    只處理外觀（底色、字型、格線、圖例、邊距），不動資料與軸的對應關係，
    因此多軸圖（花費 / 安裝 / CPI）呼叫後仍可再自行 update_layout 設定
    yaxis2、yaxis3 的位置。
    """
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=height,
        font=dict(family="-apple-system, 'Segoe UI', sans-serif",
                  size=11.5, color=TEXT_MID),
        margin=margin or dict(t=34 if (legend or title) else 12, b=22, l=10, r=10),
        hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=BORDER,
                        font=dict(color=TEXT, size=12)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0,
                    xanchor="right", x=1, font=dict(size=11),
                    bgcolor="rgba(0,0,0,0)"),
    )
    if title:
        fig.update_layout(title=dict(
            text=title, x=0.005, y=0.98, xanchor="left", yanchor="top",
            font=dict(size=12.5, color=title_color or TEXT_MID)))
    fig.update_xaxes(showgrid=False, zeroline=False,
                     linecolor=BORDER, tickfont=dict(size=11))
    fig.update_yaxes(showgrid=True, gridcolor=BORDER, zeroline=False,
                     linecolor="rgba(0,0,0,0)", tickfont=dict(size=11))
    return fig


# ══════════════════════════════════════════════════════════════════════
#  4. 共用 HTML 元件
# ══════════════════════════════════════════════════════════════════════
def section(title: str, desc: str = "") -> str:
    """區塊標題。取代 st.subheader + st.markdown("---") 的組合。"""
    d = f'<span class="of-sec-d">{desc}</span>' if desc else ""
    return (f'<div class="of-sec"><span class="of-sec-t">{title}</span>'
            f'{d}<span class="of-sec-line"></span></div>')


def sparkline(values: list, color: str = ACCENT_HI,
              width: int = 78, height: int = 34) -> str:
    """迷你走勢線（KPI 卡右側）。少於兩點就不畫。"""
    if not values or len(values) < 2:
        return ""
    pad = 3
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        max_v = min_v + 1
    step = width / (len(values) - 1)
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - pad - (v - min_v) / (max_v - min_v) * (height - 2 * pad)
        pts.append(f"{x:.1f},{y:.1f}")
    last_y = float(pts[-1].split(",")[1])
    return (
        f'<svg width="{width}" height="{height}" '
        f'style="display:block;flex-shrink:0;opacity:.85">'
        f'<polyline points="{" ".join(pts)}" stroke="{color}" stroke-width="1.6" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{width}" cy="{last_y:.1f}" r="2.2" fill="{color}"/>'
        f'</svg>'
    )


def fmt_compact(n: float) -> str:
    """八位數以上改用 M 縮寫（147,499,347 → 147.5M）。

    KPI 卡一排四張，超過十個字元的數字會把卡片撐破或被截斷；縮寫後完整
    數字放在 title 屬性，滑鼠停留就看得到。
    """
    n = float(n)
    if abs(n) >= 1e7:
        return f"{n / 1e6:.1f}M"
    return f"{n:,.0f}"


_BLOCKS = "▁▂▃▄▅▆▇█"


def spark_text(values: list, width: int = 14) -> str:
    """用區塊字元畫走勢（▁▂▄▆█），給表格儲存格用。

    表格裡不能用 SVG：AgGrid 的 React 版本要求 cellRenderer 回傳 React
    元素，塞 DOM 節點會整個元件爆掉（React error #31）。區塊字元是純文字，
    不需要 renderer，等寬字型下高低一目了然。
    """
    if not values:
        return ""
    vals = [float(v or 0) for v in values][-width:]
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return _BLOCKS[0] * len(vals)
    step = (hi - lo) / (len(_BLOCKS) - 1)
    return "".join(_BLOCKS[int((v - lo) / step)] for v in vals)


def kpi_card(label: str, value: str, delta_pct: float | None = None,
             category: str = "vol", inverse: bool = False,
             spark: list | None = None, full: str = "") -> str:
    """KPI 卡。

    label      指標名稱（不含 emoji，層級靠字級字重）
    value      已格式化的數值字串
    delta_pct  與對比期的變化百分比；None 表示沒有對比期
    category   "vol" 規模指標（藍）/ "rate" 效率指標（黃）
    inverse    True 代表「數字變大是壞事」（CPI、CPM）
    spark      近 7 天走勢，畫成右側迷你線
    full       完整數值；value 被縮寫時放進 title，hover 可看原始數字
    """
    if delta_pct is None:
        delta = '<div class="of-kpi-delta of-kpi-flat">無對比期</div>'
    else:
        is_up = delta_pct >= 0
        good = (not is_up) if inverse else is_up
        cls = "of-good" if good else "of-bad"
        arrow = "▲" if is_up else "▼"
        delta = (f'<div class="of-kpi-delta {cls}">{arrow} '
                 f'{abs(delta_pct):.1f}%<span style="color:{TEXT_DIM};'
                 f'font-weight:500"> vs 上期</span></div>')
    color = ACCENT_HI if category == "vol" else WARN
    title = f' title="{full}"' if full and full != value else ""
    return (
        f'<div class="of-kpi of-kpi-{category}">'
        f'<div class="of-kpi-body">'
        f'<div class="of-kpi-label">{label}</div>'
        f'<div class="of-kpi-value"{title}>{value}</div>'
        f'{delta}</div>'
        f'{sparkline(spark or [], color=color)}'
        f'</div>'
    )


def alert(level: str, tag: str, msg: str) -> str:
    """警示列。level：warn（注意）/ neg（惡化）/ pos（改善）。"""
    return (f'<div class="of-alert of-alert-{level}">'
            f'<span class="of-alert-tag">{tag}</span>'
            f'<span>{msg}</span></div>')


def chip(label: str, value: str, active: bool = False) -> str:
    """頂部檢視列的篩選標籤。active 代表有套用篩選（非「全部」）。"""
    cls = "of-chip of-chip-on" if active else "of-chip"
    return f'<span class="{cls}">{label} <b>{value}</b></span>'


def crumb(items: list) -> str:
    """麵包屑。items 為 [(文字, 是否為目前層級), ...]。"""
    parts = []
    for i, (text, current) in enumerate(items):
        if i:
            parts.append('<span class="of-crumb-sep">›</span>')
        cls = "of-crumb-on" if current else ""
        parts.append(f'<span class="{cls}">{text}</span>')
    return f'<div class="of-crumb">{"".join(parts)}</div>'


def status_card(label: str, value: str, sub: str, level: str) -> str:
    """sidebar 的資料新鮮度卡。level：pos / warn / neg。"""
    color = {"pos": POS, "warn": WARN, "neg": NEG}[level]
    bg = {"pos": POS_BG, "warn": WARN_BG, "neg": NEG_BG}[level]
    return (f'<div class="of-status" style="background:{bg};'
            f'border-left-color:{color}">'
            f'<div class="of-status-l">{label}</div>'
            f'<div class="of-status-v">{value}</div>'
            f'<div class="of-status-s" style="color:{color}">{sub}</div></div>')
