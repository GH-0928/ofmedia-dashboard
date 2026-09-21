# -*- coding: utf-8 -*-
"""單日歸因計算的測試。

歸因表最重要的性質是「各項目的變化加總＝整體變化」——這條不成立的話，
表上的貢獻度就是騙人的。這種事只能用數字驗，畫面看不出來。

    python dev/test_analysis.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# repo 根目錄（這個檔在 dev/ 底下，往上一層）
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import pandas as pd  # noqa: E402

import analysis  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"[通過] {name}")
    else:
        print(f"[失敗] {name}　{detail}")
        FAILED.append(name)


def make(rows):
    """rows: (日期, 媒體, campaign, 花費, 安裝)"""
    return pd.DataFrame(
        [{"date": pd.Timestamp(d), "media": m, "campaign": c,
          "spend": s, "installs": i} for d, m, c, s, i in rows])


# ── 情境：前 7 天穩定，第 8 天 Meta 的安裝翻倍 ──────────────────────
rows = []
for day in range(1, 8):
    d = f"2026-09-{day:02d}"
    rows += [(d, "Meta", "M1", 100.0, 50), (d, "Meta", "M2", 100.0, 50),
             (d, "Google", "G1", 100.0, 40)]
TARGET = "2026-09-08"
rows += [(TARGET, "Meta", "M1", 100.0, 250), (TARGET, "Meta", "M2", 100.0, 50),
         (TARGET, "Google", "G1", 100.0, 40)]
df = make(rows)
day = pd.Timestamp(TARGET)

media_tbl, cur_total, base_total = analysis.attr_table(df, day, "media", "installs")

check("當天總安裝正確", cur_total == 340, f"得到 {cur_total}")
check("基準是前 7 天日均", base_total == 140, f"得到 {base_total}")
check("各媒體變化加總＝整體變化",
      abs(media_tbl["delta"].sum() - (cur_total - base_total)) < 1e-9,
      f"{media_tbl['delta'].sum()} vs {cur_total - base_total}")
check("貢獻度加總為 100%",
      abs(media_tbl["share"].sum() - 100) < 1e-6,
      f"得到 {media_tbl['share'].sum()}")
check("變化最大的是 Meta", str(media_tbl.iloc[0]["name"]) == "Meta",
      f"得到 {media_tbl.iloc[0]['name']}")
check("沒有變化的媒體 delta 為 0",
      abs(float(media_tbl[media_tbl["name"] == "Google"]["delta"].iloc[0])) < 1e-9)

cmp_tbl, _, _ = analysis.attr_table(df, day, "campaign", "installs")
check("Campaign 層也自洽",
      abs(cmp_tbl["delta"].sum() - (cur_total - base_total)) < 1e-9)
check("指到正確的 Campaign", str(cmp_tbl.iloc[0]["name"]) == "M1",
      f"得到 {cmp_tbl.iloc[0]['name']}")

# ── 新項目：基準為 0 時不能算出無限大的百分比 ──────────────────────
rows2 = list(rows) + [(TARGET, "TikTok", "T1", 500.0, 300)]
df2 = make(rows2)
t2, cur2, base2 = analysis.attr_table(df2, day, "media", "installs")
new_row = t2[t2["name"] == "TikTok"].iloc[0]
check("新項目的變化百分比標成 NaN（顯示為「新增」）",
      pd.isna(new_row["pct"]), f"得到 {new_row['pct']}")
check("新項目仍算得出貢獻度", new_row["share"] > 0)

# ── 異常偵測：門檻與絕對量下限 ─────────────────────────────────────
found = analysis.day_anomalies(df, 15.0)
inst = [a for a in found if a["col"] == "installs"]
check("15% 門檻抓得到這天的安裝暴增", len(inst) == 1, f"抓到 {len(inst)} 筆")
if inst:
    a = inst[0]
    check("指名的媒體正確", a["media"] == "Meta", f"得到 {a['media']}")
    check("指名的 Campaign 正確", a["campaign"] == "M1", f"得到 {a['campaign']}")
    check("變化幅度算對（140 → 340 = +143%）",
          abs(a["pct"] - 142.857) < 0.1, f"得到 {a['pct']}")

check("門檻拉到 200% 就不該報", len(
    [a for a in analysis.day_anomalies(df, 200.0) if a["col"] == "installs"]) == 0)

# 小數字的大百分比要被絕對量下限擋掉：40 → 33 是 -17%，但只差 7 個安裝
small = make([(f"2026-09-{d:02d}", "Meta", "M1", 10.0, 40) for d in range(1, 8)]
             + [(TARGET, "Meta", "M1", 10.0, 33)])
check("小數字的大百分比不報（絕對量不足）",
      len([a for a in analysis.day_anomalies(small, 15.0)
           if a["col"] == "installs"]) == 0)

# ── 花費驟減也要抓得到 ─────────────────────────────────────────────
drop = make([(f"2026-09-{d:02d}", "Meta", "M1", 1000.0, 100) for d in range(1, 8)]
            + [(TARGET, "Meta", "M1", 200.0, 100)])
spend_alerts = [a for a in analysis.day_anomalies(drop, 15.0) if a["col"] == "spend"]
check("花費驟減抓得到", len(spend_alerts) == 1, f"抓到 {len(spend_alerts)} 筆")
if spend_alerts:
    check("方向是負的", spend_alerts[0]["pct"] < 0)

# ── 基準期不足 7 天時用實際天數當分母 ──────────────────────────────
short = make([("2026-09-01", "Meta", "M1", 100.0, 50),
              ("2026-09-02", "Meta", "M1", 100.0, 50),
              ("2026-09-03", "Meta", "M1", 100.0, 150)])
_, cur3, base3 = analysis.attr_table(short, pd.Timestamp("2026-09-03"),
                                     "media", "installs")
check("基準期不足時用實際天數平均（不是硬除 7）", base3 == 50, f"得到 {base3}")

print("\n結果：", "全部通過" if not FAILED else f"{len(FAILED)} 項失敗")
sys.exit(0 if not FAILED else 1)
