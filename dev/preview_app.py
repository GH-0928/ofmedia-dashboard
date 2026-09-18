# -*- coding: utf-8 -*-
"""本機視覺預覽：用假資料跑真正的 app.py，不需要 Google Sheet 憑證與密碼。

只用於開發期間檢查版面，不會進 repo。數字是亂數，版面與互動是真的。
"""
import os
import sys
import types

import numpy as np
import pandas as pd
import streamlit as st

# repo 根目錄（這個檔在 dev/ 底下，往上一層）
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

rng = np.random.default_rng(7)
MEDIA = ["Meta", "Google", "ASA", "TikTok", "Applovin", "Moloco"]
COUNTRY = ["US", "JP", "KR", "TW", "BR", "MX", "ID", "PH"]
OS = ["IOS", "AND"]
DATES = pd.date_range("2026-08-01", "2026-09-17", freq="D")
# 各媒體的量級差異拉開，才看得出預算集中與 CPI 排行的實際效果
WEIGHT = {"Meta": 6.0, "Google": 3.0, "ASA": 1.6, "TikTok": 1.0,
          "Applovin": 0.6, "Moloco": 0.4}


def make(n_campaign=3, extra=None):
    rows = []
    for d in DATES:
        # 讓後半段花費往上走，趨勢圖才有起伏
        ramp = 1 + (d - DATES[0]).days / len(DATES)
        for m in MEDIA:
            for c in rng.choice(COUNTRY, 3, replace=False):
                for o in OS:
                    for i in range(n_campaign):
                        w = WEIGHT[m] * ramp
                        imp = int(rng.integers(2000, 40000) * w)
                        clk = int(imp * rng.uniform(0.006, 0.04))
                        ins = int(clk * rng.uniform(0.03, 0.22))
                        row = {
                            "date": d, "media": m, "os": o, "country": str(c),
                            "campaign": f"{m}_CP{i}",
                            "spend": round(float(rng.uniform(20, 400) * w), 2),
                            "impressions": imp, "clicks": clk, "installs": ins,
                        }
                        if extra:
                            row.update(extra(m, i))
                        rows.append(row)
    return pd.DataFrame(rows)


UNIFIED = make()

# 製造幾種異常，讓「異常警示」區塊在預覽時有東西可看：
#   Meta 本月成本惡化（花費翻倍、安裝砍半 → CPI 暴增、預算集中）
#   TikTok 本月量體崩掉（安裝剩兩成 → 安裝驟降）
_sep = pd.Timestamp("2026-09-01")
_m = (UNIFIED["media"] == "Meta") & (UNIFIED["date"] >= _sep)
UNIFIED.loc[_m, "spend"] *= 2.2
UNIFIED.loc[_m, "installs"] = (UNIFIED.loc[_m, "installs"] * 0.45).astype(int)
_t = (UNIFIED["media"] == "TikTok") & (UNIFIED["date"] >= _sep)
UNIFIED.loc[_t, "installs"] = (UNIFIED.loc[_t, "installs"] * 0.2).astype(int)
META = make(2, lambda m, i: {
    "ad_group": f"AG{i}", "ad": f"AD{i}_{rng.integers(0, 3)}",
    "status": rng.choice(["active", "paused", "learning"])})
META["media"] = "Meta"
ASA = make(2, lambda m, i: {
    "keyword": f"fish game {i}", "search_term": f"fishing shooter {i}",
    "match_type": rng.choice(["exact", "broad", "search_match"])})
ASA["media"] = "ASA"
GOOGLE = make(2, lambda m, i: {
    "network": rng.choice(["Search", "Display", "YouTube", "Search partners"]),
    "ad_group": f"GAG{i}"})
GOOGLE["media"] = "Google"

fake_data = types.ModuleType("data")
fake_data.load_unified = lambda: UNIFIED.copy()
fake_data.load_meta_raw = lambda: META.copy()
fake_data.load_asa_raw = lambda: ASA.copy()
fake_data.load_google_raw = lambda: GOOGLE.copy()
fake_data.RAW_TABS = {}
sys.modules["data"] = fake_data

fake_store = types.ModuleType("calendar_store")
fake_store.list_ops = lambda: [
    {"id": "1", "date": "2026-09-09", "media": "Meta", "op_type": "調預算",
     "campaign": "Meta_CP0", "note": "日預算 500 → 800"},
    {"id": "2", "date": "2026-09-12", "media": "Google", "op_type": "換素材",
     "campaign": "Google_CP1", "note": "上新影片素材三支，舊素材保留觀察"},
    {"id": "3", "date": "2026-09-15", "media": "ASA", "op_type": "關鍵字調整",
     "campaign": "ASA_CP2", "note": "加 12 組長尾字，出價 1.2"},
]
sys.modules["calendar_store"] = fake_store

fake_cal = types.ModuleType("calendar_view")
fake_cal.render = lambda: st.info("（預覽模式不載入行事曆）")
sys.modules["calendar_view"] = fake_cal

# 跳過密碼登入
st.session_state["authed"] = True

with open(os.path.join(BASE, "app.py"), encoding="utf-8") as f:
    code = f.read()
exec(compile(code, os.path.join(BASE, "app.py"), "exec"), {"__name__": "__main__"})
