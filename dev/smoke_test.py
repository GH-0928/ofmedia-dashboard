# -*- coding: utf-8 -*-
"""離線煙霧測試：用假資料把 app.py 整個跑過一遍，確認沒有例外。

不需要 Google Sheet 憑證與登入密碼 —— data / calendar_store / calendar_view
三個模組在 app.py 匯入前先換成假的，登入則直接把 session_state 設成已登入。
"""
import io
import os
import sys
import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# repo 根目錄（這個檔在 dev/ 底下，往上一層）
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
MEDIA = ["Meta", "Google", "ASA", "TikTok", "Applovin", "Moloco"]
COUNTRY = ["US", "JP", "KR", "TW", "BR", "MX", "ID", "PH"]
OS = ["IOS", "AND"]
DATES = pd.date_range("2026-08-01", "2026-09-17", freq="D")


def _make(n_campaign=3, extra=None):
    rows = []
    for d in DATES:
        for m in MEDIA:
            for c in rng.choice(COUNTRY, 3, replace=False):
                for o in OS:
                    for i in range(n_campaign):
                        imp = int(rng.integers(500, 60000))
                        clk = int(imp * rng.uniform(0.005, 0.05))
                        ins = int(clk * rng.uniform(0.02, 0.25))
                        row = {
                            "date": d, "media": m, "os": o, "country": str(c),
                            "campaign": f"{m}_CP{i}",
                            "spend": round(float(rng.uniform(5, 900)), 2),
                            "impressions": imp, "clicks": clk, "installs": ins,
                        }
                        if extra:
                            row.update(extra(m, i))
                        rows.append(row)
    return pd.DataFrame(rows)


UNIFIED = _make()

META = _make(2, lambda m, i: {
    "ad_group": f"AG{i}", "ad": f"AD{i}_{rng.integers(0, 3)}",
    "status": rng.choice(["active", "paused", "learning", "disapproved"]),
})
META["media"] = "Meta"

ASA = _make(2, lambda m, i: {
    "keyword": f"kw_{i}", "search_term": f"term_{i}",
    "match_type": rng.choice(["exact", "broad", "search_match"]),
})
ASA["media"] = "ASA"

GOOGLE = _make(2, lambda m, i: {
    "network": rng.choice(["Search", "Display", "YouTube", "Search partners"]),
    "ad_group": f"GAG{i}",
})
GOOGLE["media"] = "Google"

# ── 換掉三個會連外的模組 ─────────────────────────────────────────
fake_data = types.ModuleType("data")
fake_data.load_unified = lambda: UNIFIED.copy()
fake_data.load_meta_raw = lambda: META.copy()
fake_data.load_asa_raw = lambda: ASA.copy()
fake_data.load_google_raw = lambda: GOOGLE.copy()
fake_data.RAW_TABS = {}
sys.modules["data"] = fake_data

fake_store = types.ModuleType("calendar_store")
fake_store.list_ops = lambda: [
    {"id": "1", "date": "2026-09-10", "media": "Meta", "op_type": "調預算",
     "campaign": "Meta_CP0", "note": "日預算 500 → 800"},
    {"id": "2", "date": "2026-09-12", "media": "Google", "op_type": "換素材",
     "campaign": "Google_CP1", "note": "上新影片素材三支，舊素材同時保留觀察"},
]
sys.modules["calendar_store"] = fake_store

fake_cal = types.ModuleType("calendar_view")
fake_cal.render = lambda: None
sys.modules["calendar_view"] = fake_cal

# AppTest 沒有前端，AgGrid 永遠回傳「沒有選取」，選取之後的分支（單項走勢、
# 多項對比、超過五項只畫前五）測不到。這裡把 data_grid 換成假的，讓它依
# FAKE_SEL 指定的數量回傳前 n 列，就能把那些路徑跑過。
import grid as _grid  # noqa: E402

FAKE_SEL = {}
def _fake_data_grid(df, cols, key, **kw):
    n = FAKE_SEL.get("*", 0)
    return df.head(n)


_grid.data_grid = _fake_data_grid

from streamlit.testing.v1 import AppTest  # noqa: E402


def run(label, state=None, timeout=120, select=0):
    FAKE_SEL["*"] = select
    at = AppTest.from_file(os.path.join(BASE, "app.py"), default_timeout=timeout)
    at.secrets["auth"] = {"password": "x"}
    at.session_state["authed"] = True
    for k, v in (state or {}).items():
        at.session_state[k] = v
    at.run()
    if at.exception:
        print(f"[失敗] {label}")
        for e in at.exception:
            print("   ", str(e.value)[:600])
        return at, False
    print(f"[通過] {label}")
    return at, True


ok = True
at, r = run("預設畫面（全部篩選＝全部）")
ok &= r

if r:
    # 四個分頁都渲染了嗎
    tabs = [t.label for t in at.tabs] if hasattr(at, "tabs") else []
    print("    分頁：", tabs)
    print("    表格數：", len(at.dataframe))
    print("    圖表數：", len(at.get("plotly_chart")))
    print("    按鈕數：", len(at.button))

# 篩選互動
_, r = run("媒體＝Meta", {"f_media": "Meta"})
ok &= r
_, r = run("OS＝iOS", {"f_os": "iOS"})
ok &= r
_, r = run("國家＝US", {"f_country": "US"})
ok &= r
_, r = run("期間＝近 7 天", {"f_date_mode": "近 7 天"})
ok &= r
_, r = run("期間＝昨日（單日）", {"f_date_mode": "昨日"})
ok &= r

# 深度頁各媒體
for m in ["ASA", "Google", "TikTok", "Applovin", "Moloco"]:
    _, r = run(f"媒體深度＝{m}", {"deep_tab": m})
    ok &= r

# Meta 下鑽第二、三層
_, r = run("Meta 下鑽到 Ad Group", {"meta_drill_campaign": "Meta_CP0"})
ok &= r
_, r = run("Meta 下鑽到素材", {"meta_drill_campaign": "Meta_CP0",
                                    "meta_drill_ad_group": "AG0"})
ok &= r

# 行事曆分頁
_, r = run("行事曆・待辦分頁", {"_main_section": "行事曆待辦"})
ok &= r

# 空資料：篩到沒有任何一列
_, r = run("極端篩選（可能無資料）",
           {"f_country": "US", "f_media": "Moloco", "f_os": "其他"})
ok &= r

# 選取之後的分支（靠 FAKE_SEL 假裝使用者點了 n 列）
for n, desc in [(1, "選 1 列：單項走勢"), (3, "選 3 列：CPI 對比"),
                (6, "選 6 列：只畫前 5")]:
    _, r = run(f"Meta Campaign {desc}", select=n)
    ok &= r
_, r = run("Meta 素材層選 1 列", {"meta_drill_campaign": "Meta_CP0",
                                  "meta_drill_ad_group": "AG0"}, select=1)
ok &= r
_, r = run("TikTok Campaign 選 2 列", {"deep_tab": "TikTok"}, select=2)
ok &= r
_, r = run("ASA 關鍵字選 1 列", {"deep_tab": "ASA"}, select=1)
ok &= r
_, r = run("Google Ad Group 選 1 列", {"deep_tab": "Google"}, select=1)
ok &= r

# 快篩
for m in ["需要注意", "表現好"]:
    _, r = run(f"Meta 快篩＝{m}", {"qf_meta_campaign": m})
    ok &= r
_, r = run("TikTok 快篩＝需要注意", {"deep_tab": "TikTok",
                                     "qf_grid_cmp_TikTok": "需要注意"})
ok &= r

# 單日歸因
_, r = run("單日歸因：安裝", {"attr_day": "2026-09-12"})
ok &= r
_, r = run("單日歸因：花費", {"attr_day": "2026-09-12", "attr_metric": "花費"})
ok &= r
_, r = run("單日歸因：期間第一天（基準期不足 7 天）", {"attr_day": "2026-09-01"})
ok &= r
_, r = run("單日歸因 + 點一個 Campaign 看走勢",
           {"attr_day": "2026-09-12"}, select=1)
ok &= r
_, r = run("趨勢圖依媒體堆疊", {"trend_view": "依媒體"})
ok &= r
for th in ["15%", "20%", "30%"]:
    _, r = run(f"警示門檻 {th}", {"alert_threshold": th})
    ok &= r

print("\n結果：", "全部通過" if ok else "有失敗")
sys.exit(0 if ok else 1)
