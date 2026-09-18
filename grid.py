# -*- coding: utf-8 -*-
"""表格元件層 ── AgGrid 的統一封裝。

為什麼不用 `st.dataframe`：它的選取 UI 固定是列首那個小圓圈，點名稱或
任何儲存格都不會選中，下鑽時每次都要瞄準那個八畫素的目標。AgGrid 可以
「點整列任一處即選取」，這是媒體深度頁能不能順手用的關鍵。

這個模組只負責「把 DataFrame 畫成表格並回傳選取的列」，欄位格式用宣告的
方式描述（見 `col()`），樣式一律取自 theme.py 的 token。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from st_aggrid import (AgGrid, GridOptionsBuilder, GridUpdateMode,
                       JsCode, StAggridTheme)

import theme

# ── 顯示格式（在瀏覽器端格式化，欄位底層維持數值，排序才會正確）──────
_FMT_JS = {
    "money": JsCode("function(p){return p.value==null?'':'$'+Number(p.value)"
                    ".toLocaleString('en-US',{maximumFractionDigits:0});}"),
    "cost": JsCode("function(p){return p.value==null?'':'$'+Number(p.value)"
                   ".toFixed(2);}"),
    "int": JsCode("function(p){return p.value==null?'':Number(p.value)"
                  ".toLocaleString('en-US');}"),
    "pct": JsCode("function(p){return p.value==null?'':Number(p.value)"
                  ".toFixed(2)+'%';}"),
}
_NUMERIC = set(_FMT_JS)

# 占比欄：用儲存格背景的漸層畫長條。AgGrid 的 React 版本要求 cellRenderer
# 回傳 React 元素，回傳 DOM 節點會讓整個元件掛掉（React error #31），所以
# 這裡改走 cellStyle —— 它只回傳純物件，不碰 DOM。
_BAR_STYLE_JS = JsCode(
    "function(p){const v=Math.max(0,Math.min(100,Number(p.value)||0));"
    "return {background:'linear-gradient(to right, rgba(59,130,246,0.55) '"
    "+v+'%, transparent '+v+'%)'};}"
)

# 走勢欄：值在 Python 端就轉成區塊字元字串（見 theme.spark_text），
# 這裡只調字距與顏色。
_SPARK_STYLE = {"letter-spacing": "-1px", "color": theme.ACCENT_HI,
                "font-size": "15px"}

def col(field: str, label: str, fmt: str = "text", *, width: int | None = None,
        flex: int | None = None, help: str | None = None,
        pinned: str | None = None) -> dict:
    """描述一個欄位。

    fmt："text" / "money"（整數金額）/ "cost"（兩位小數金額）/ "int" /
         "pct"（資料本身是 0-100）/ "bar"（占比，儲存格底色畫成長條）/
         "spark"（走勢，值是數列，會轉成區塊字元）
    pinned："left" 可把名稱欄釘在左邊，水平捲動時不會滑走
    """
    return {"field": field, "label": label, "fmt": fmt, "width": width,
            "flex": flex, "help": help, "pinned": pinned}


def _grid_theme() -> StAggridTheme:
    """AG Grid v33 Theming API：把表格外觀接到 theme.py 的 token。"""
    return (
        StAggridTheme(base="balham")
        .withParams(
            backgroundColor=theme.SURFACE,
            foregroundColor=theme.TEXT,
            chromeBackgroundColor=theme.SURFACE_2,
            headerBackgroundColor=theme.SURFACE_2,
            headerTextColor=theme.TEXT_MID,
            borderColor=theme.BORDER,
            rowHoverColor=theme.SURFACE_2,
            selectedRowBackgroundColor="rgba(59,130,246,0.20)",
            accentColor=theme.ACCENT,
            fontSize=13,
            headerFontSize=12,
            wrapperBorderRadius=9,
            browserColorScheme="dark",
        )
        .withParts("colorSchemeDark")
    )


def data_grid(df: pd.DataFrame, cols: list, key: str, *,
              selection: str = "single", max_height: int = 520,
              row_height: int = 34) -> pd.DataFrame:
    """畫一張可點整列選取的表格，回傳被選取的列（沒選就是空 DataFrame）。

    selection："single" 單選 / "multi" 可用 Ctrl、Shift 複選 / "none" 唯讀
    """
    fields = [c["field"] for c in cols if c["field"] in df.columns]
    data = df[fields].copy()

    # 走勢欄：把數列轉成區塊字元字串
    for c in cols:
        if c["fmt"] == "spark" and c["field"] in data.columns:
            data[c["field"]] = data[c["field"]].apply(
                lambda v: theme.spark_text(v if isinstance(v, (list, tuple)) else []))

    gb = GridOptionsBuilder.from_dataframe(data)
    gb.configure_default_column(sortable=True, filter=False, resizable=True,
                                suppressMovable=True)
    for c in cols:
        if c["field"] not in data.columns:
            continue
        kw = {}
        if c["fmt"] in _NUMERIC:
            kw["type"] = ["numericColumn"]
            kw["valueFormatter"] = _FMT_JS[c["fmt"]]
        elif c["fmt"] == "bar":
            kw["type"] = ["numericColumn"]
            kw["valueFormatter"] = _FMT_JS["pct"]
            kw["cellStyle"] = _BAR_STYLE_JS
        elif c["fmt"] == "spark":
            kw["cellStyle"] = _SPARK_STYLE
            kw["sortable"] = False
        # minWidth 是必要的保護：容器一窄（側欄展開、視窗縮小），沒有下限的
        # 欄位會被壓成兩三個字的寬度，整張表變成無法閱讀的色塊。給了下限之後
        # 窄畫面會改成水平捲動，欄位維持可讀。
        if c["width"]:
            kw["width"] = c["width"]
            kw["minWidth"] = c["width"]
        if c["flex"]:
            kw["flex"] = c["flex"]
            kw["minWidth"] = c.get("min_width") or 170
        if c["pinned"]:
            kw["pinned"] = c["pinned"]
        if c["help"]:
            kw["headerTooltip"] = c["help"]
        gb.configure_column(c["field"], headerName=c["label"], **kw)

    opts = gb.build()
    opts["rowHeight"] = row_height
    opts["headerHeight"] = 36
    opts["suppressCellFocus"] = True          # 不顯示單一儲存格的焦點框
    opts["suppressDragLeaveHidesColumns"] = True
    if selection == "none":
        opts.pop("rowSelection", None)
    else:
        # v32.2 之後 rowSelection 是物件；enableClickSelection 才是
        # 「點列任一處就選取」的開關，checkboxes=False 拿掉列首的小方框。
        opts["rowSelection"] = {
            "mode": "multiRow" if selection == "multi" else "singleRow",
            "checkboxes": False,
            "headerCheckbox": False,
            "enableClickSelection": True,
            # 多選仍要按 Ctrl / Shift，否則連點兩列會變成兩列都選中
            "enableSelectionWithoutKeys": False,
        }

    # 高度自己算：AgGrid 的 autoHeight 會在元件外框留一段空白，直接給精確
    # 高度（表頭 + 列數 × 列高）才會貼齊內容；超過上限就固定高度讓它捲動。
    exact = 38 + len(data) * row_height + 4
    height = min(exact, max_height)

    grid = AgGrid(
        data,
        gridOptions=opts,
        theme=_grid_theme(),
        height=height,
        allow_unsafe_jscode=True,          # 數字格式與占比長條需要
        # 只有選取變動才回 Python 端重跑；排序、捲動留在前端做。
        # data_return_mode 不能用 MINIMAL —— 那會連 selected_rows 一起省掉，
        # 表格看起來有選中，Python 這邊卻永遠收到空的。
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        show_toolbar=False,
        show_search=False,
        show_download_button=False,
        key=key,
    )

    # 元件還沒回傳資料時（例如 AppTest 這種沒有前端的情境，或首次渲染）
    # 取不到 selected_rows，這時一律當成「沒有選取」。
    try:
        sel = grid["selected_rows"]
    except (KeyError, TypeError):
        sel = None
    if sel is None:
        return pd.DataFrame()
    if isinstance(sel, list):
        return pd.DataFrame(sel)
    return sel


def selected_values(sel: pd.DataFrame, field: str) -> list:
    """從選取結果取出某欄的值，維持表格上的順序。"""
    if sel is None or sel.empty or field not in sel.columns:
        return []
    return sel[field].tolist()
