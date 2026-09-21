# -*- coding: utf-8 -*-
"""單日變化歸因的計算 ── 不碰畫面，純資料。

抽出來是為了能直接對它寫測試：歸因表最重要的性質是「各項目的變化加總
等於整體變化」，那必須用真的數字驗，不能只靠畫面看起來對。
"""
from __future__ import annotations

import pandas as pd

# 單日歸因用的欄位名稱與基準天數
BASELINE_DAYS = 7
METRIC_COLS = {"安裝": "installs", "花費": "spend"}


def attr_table(df: pd.DataFrame, day: pd.Timestamp, group_col: str,
                metric_col: str) -> tuple:
    """把某一天與前幾天的日均相比，算出各項目的變化與貢獻度。

    基準用前 7 天的「日平均」而不是前一天：前一天本身可能就是異常值，
    拿它當基準會互相抵銷，該看到的跳動反而不見。

    回傳 (明細表, 當天總值, 基準總值)。
    """
    dates = df["date"].dt.normalize()
    cur = df[dates == day]
    base_start = day - pd.Timedelta(days=BASELINE_DAYS)
    base = df[(dates >= base_start) & (dates <= day - pd.Timedelta(days=1))]
    # 基準期可能不足 7 天（期間開頭那幾天），用實際有資料的天數當分母
    base_days = max(base["date"].dt.normalize().nunique(), 1)

    c = cur.groupby(group_col)[metric_col].sum()
    b = base.groupby(group_col)[metric_col].sum() / base_days
    idx = c.index.union(b.index)
    out = pd.DataFrame({
        "name": idx,
        "cur": c.reindex(idx, fill_value=0).values,
        "base": b.reindex(idx, fill_value=0).values,
    })
    out["delta"] = out["cur"] - out["base"]
    total_delta = out["delta"].sum()
    # 貢獻度＝這個項目的變化佔整體變化的比例；整體幾乎沒變時算貢獻沒有意義
    out["share"] = (out["delta"] / total_delta * 100) if abs(total_delta) > 1e-9 else 0.0
    # 基準為 0 代表當天才開始跑，變化百分比會是無限大，改標成「新增」
    out["pct"] = out.apply(
        lambda r: (r["delta"] / r["base"] * 100) if r["base"] > 0 else float("nan"),
        axis=1)
    out = out.reindex(out["delta"].abs().sort_values(ascending=False).index)
    return out, float(cur[metric_col].sum()), float(b.sum())


def day_anomalies(df: pd.DataFrame, threshold_pct: float) -> list:
    """找出期間內偏離前 7 日均值超過門檻的日子，並指出主要貢獻者。

    只看百分比會被小數字騙（40 個安裝掉到 33 就是 -17%），所以另外要求
    變化的絕對量夠大才算數。
    """
    MIN_ABS = {"installs": 100, "spend": 500}
    if df.empty:
        return []
    dates = sorted(df["date"].dt.normalize().unique())
    found = []
    for label, col in METRIC_COLS.items():
        for day in dates:
            table, cur_total, base_total = attr_table(df, day, "media", col)
            if base_total <= 0:
                continue
            delta = cur_total - base_total
            pct = delta / base_total * 100
            if abs(pct) < threshold_pct or abs(delta) < MIN_ABS[col]:
                continue
            top = table.iloc[0] if not table.empty else None
            # Campaign 必須從「貢獻最大的那個媒體」裡面找。直接對全體取最大
            # 會出現「主要來自 ASA，Campaign：Google_CP2」這種不同家的組合，
            # 兩個都是對的數字，湊在一句話裡卻會讓人誤會。
            cmp_top = None
            if top is not None:
                sub = df[df["media"] == top["name"]]
                cmp_tbl, _, _ = attr_table(sub, day, "campaign", col)
                cmp_top = cmp_tbl.iloc[0] if not cmp_tbl.empty else None
            found.append({
                "day": day, "metric": label, "col": col,
                "cur": cur_total, "base": base_total, "pct": pct,
                "media": str(top["name"]) if top is not None else "",
                "media_delta": float(top["delta"]) if top is not None else 0.0,
                "media_share": float(top["share"]) if top is not None else 0.0,
                "campaign": str(cmp_top["name"]) if cmp_top is not None else "",
                "campaign_delta": float(cmp_top["delta"]) if cmp_top is not None else 0.0,
            })
    found.sort(key=lambda a: (a["day"], -abs(a["pct"])))
    return found
