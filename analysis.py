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


# ══════════════════════════════════════════════════════════════════════
#  逐日變化表
# ══════════════════════════════════════════════════════════════════════
WEEKDAY_ZH = ["一", "二", "三", "四", "五", "六", "日"]

# 基準的兩種取法：跟前一天比看突變，跟前 7 天日均比看趨勢偏離
BASIS_PREV = "比前一日"
BASIS_AVG = f"比前 {BASELINE_DAYS} 日均值"


def _baseline(frame: pd.DataFrame, basis: str) -> pd.DataFrame:
    """把每日數列換成對應的基準線。

    closed="left" 是關鍵：滾動平均必須排除當天，否則當天的異常值會被算進
    自己的基準裡，把差異稀釋掉。
    """
    if basis == BASIS_PREV:
        return frame.shift(1)
    return frame.rolling(BASELINE_DAYS, min_periods=1, closed="left").mean()


def _top_source(df: pd.DataFrame, metric_col: str, basis: str,
                index) -> pd.DataFrame:
    """每天變化最大的那個 campaign（含它的變化量）。

    整張表一次算完，不逐日跑 groupby —— 期間拉到一個月、兩個指標的話，
    逐日做會是幾十次 groupby。
    """
    import numpy as np

    pv = df.pivot_table(index="day", columns="campaign", values=metric_col,
                        aggfunc="sum", fill_value=0).reindex(index, fill_value=0)
    delta = (pv - _baseline(pv, basis))
    arr = delta.to_numpy(dtype="float64")
    names, values = [], []
    for row in arr:
        if np.all(np.isnan(row)) or row.size == 0:
            names.append("")
            values.append(float("nan"))
            continue
        pos = int(np.nanargmax(np.abs(row)))
        names.append(str(delta.columns[pos]))
        values.append(float(row[pos]))
    return pd.DataFrame({"name": names, "delta": values}, index=index)


def daily_changes(df: pd.DataFrame, basis: str = BASIS_PREV) -> pd.DataFrame:
    """逐日變化表：每天的花費與安裝、跟基準的差，以及主要變化來源。

    回傳的欄位都是數值型別（顯示格式交給表格層），日期另外給一個帶星期的
    標籤，週末效應才看得出來。
    """
    if df.empty:
        return pd.DataFrame()
    d = df.copy()
    d["day"] = d["date"].dt.normalize()
    daily = d.groupby("day")[["spend", "installs"]].sum().sort_index()
    base = _baseline(daily, basis)

    media_of = d.drop_duplicates("campaign").set_index("campaign")["media"].to_dict()
    out = pd.DataFrame(index=daily.index)
    out["day"] = daily.index
    out["day_label"] = [f"{t.strftime('%m-%d')} {WEEKDAY_ZH[t.weekday()]}"
                        for t in daily.index]

    for col in ("spend", "installs"):
        out[col] = daily[col]
        delta = daily[col] - base[col]
        out[f"{col}_delta"] = delta
        # 基準為 0（期間第一天、或那天之前完全沒跑）時百分比沒有意義
        out[f"{col}_pct"] = (delta / base[col] * 100).replace(
            [float("inf"), float("-inf")], float("nan"))
        top = _top_source(d, col, basis, daily.index)
        out[f"{col}_src"] = [
            f"{n}（{media_of.get(n, '?')}）" if n else ""
            for n in top["name"]]
        out[f"{col}_src_delta"] = top["delta"].values

    # 最新的日子放最上面：每天進來先看昨天發生什麼事
    return out.sort_index(ascending=False).reset_index(drop=True)
