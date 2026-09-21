# OFmedia 廣告儀表板（雲端版）

Ocean Fishooter UA 投放儀表板，以 6 個媒體（Meta / ASA / Google / TikTok / Applovin / Moloco）的 `_raw` 分頁為資料源。

## 部署網址
- 自有網域（階段 2）：`https://ofmedia.garichy.com`
- Streamlit Cloud 備援：後續會有
- 密碼：見 Secrets

## 畫面結構

左側 sidebar 放主導覽（廣告數據 / 行事曆・待辦）與全站篩選（期間、媒體、OS、國家），篩選在四個分頁之間共用。

廣告數據分成四個分頁：

| 分頁 | 內容 |
|---|---|
| 投放總覽 | 八個 KPI（規模四個、效率四個，含對比期變化與近 7 天走勢）、異常警示、每日趨勢（含廣告操作標記）、**逐日變化表＋單日歸因**、媒體分布、期間內操作紀錄 |
| 媒體對比 | 六媒體並排對比表（花費占比畫成長條）、CPI 排行 |
| 地區・OS | iOS 與 Android 對照、國家表現前 15 名、國家 × 媒體 CPI 熱力圖 |
| 媒體深度 | Meta 三層下鑽（Campaign → Ad Group → 素材）、ASA 關鍵字與搜尋詞、Google Network 與 Ad Group，其餘媒體看 Campaign 排行 |

### 逐日變化（哪天出事、誰造成的）

回答「某天安裝突然變多、花費突然變少，是哪個媒體、哪個 Campaign 造成的」。

- **期間內每一天都列出來**，不必先在趨勢圖上找到跳動才點進去。列數跟著篩選期間走
- 一列同時給**花費與安裝**：兩者的組合（花費降但安裝升）往往才是重點，分開看會藏起來
- **基準可切換**：`比前一日` 抓突變、`比前 7 日均值` 抓偏離常態。後者用滾動平均且排除當天，
  不會被前一天自己的異常帶偏
- **主要變化來源**直接寫在列上：花費與安裝各一行，`金額 → Campaign（媒體）`。
  金額排在名稱前面，欄寬不夠時被截掉的是名稱尾巴而不是關鍵數字，完整內容在 tooltip
- **點任一列**展開該日完整排行：媒體層與 Campaign 層，附貢獻度長條
  （貢獻度＝該項目的變化佔整體變化的比例；負值代表它往反方向動、在抵銷整體變化，長條轉紅）
- 點每日趨勢圖上的某一天，效果等同點那一列

日期帶星期（`09-20 日`），週末效應一眼看得出來。

**異常警示不處理單日跳動** —— 逐日表已經全部攤開，警示再講一次只是洗版，
也省掉「門檻該設幾 %」這個永遠喬不準的問題。警示只留期間層級的：
CPI 惡化、安裝驟降、預算集中。

### 媒體深度頁的操作方式

- **點表格任一列**（列上任何位置都可以）＝ 看該項目的 14 天走勢，不會換層
- **Ctrl 或 Shift 複選 2～5 列** ＝ 改畫多條 CPI 疊圖做對比，超過 5 個只畫前 5 個
- **換層要按「查看 ⟨名稱⟩ 的 Ad Group →」按鈕**，選取與下鑽分開，才不會點一下就跳走
- **麵包屑每層可點**，直接跳回上層
- **快篩**：`需要注意` 是昨日 CPI 比 7 日水準貴三成以上、或花費破百卻不到 5 個安裝；`表現好` 是昨日 CPI 比 7 日水準便宜兩成以上且安裝滿 10

## 檔案

| 檔案 | 用途 |
|---|---|
| `app.py` | 主程式：資料篩選、各分頁的圖表與表格 |
| `theme.py` | **視覺系統的唯一來源**：色階、間距、字級、圖表主題、共用 HTML 元件 |
| `grid.py` | **表格元件層**：AgGrid 的統一封裝，欄位用 `grid.col()` 宣告，回傳被選取的列 |
| `analysis.py` | 逐日變化與單日歸因的計算（純資料，不碰畫面，可直接測試）|
| `data.py` | Google Sheet 讀取與欄位統合 |
| `auth.py` | 密碼登入閘 |
| `calendar_view.py` / `calendar_store.py` | 行事曆・待辦 |
| `.streamlit/config.toml` | Streamlit 原生元件的主題色 |
| `dev/` | 開發工具：離線煙霧測試與假資料預覽（不需要憑證與密碼，見 `dev/README.md`）|

## 開發流程

改完 UI 照這個順序驗：

```bash
python dev/test_analysis.py                                # 歸因計算的正確性（數字層級）
python dev/smoke_test.py                                   # 31 個情境跑一遍，抓例外
streamlit run dev/preview_app.py --server.port 8599        # 假資料預覽，看版面與互動
```

兩支都不需要 Google Sheet 憑證與登入密碼。細節見 `dev/README.md`。

## 維護須知

- **改外觀先看 `theme.py`。** `app.py` 裡不寫 hex 色碼，一律引用 token；`config.toml` 的主題色要跟 `theme.py` 同步，否則原生元件（表格、輸入框）會和自訂卡片不同色系。
- **表格一律走 `grid.data_grid()`，不要用 `st.dataframe`**。`st.dataframe` 的選取 UI 固定是列首那個小圓圈，點名稱不會有反應；AgGrid 才能點整列。
- **表格欄位保留數值型別**，顯示格式交給 `grid.col(..., "money" / "cost" / "pct")` 在瀏覽器端處理。若先把數字轉成 `"$1,234"` 字串，點欄位排序會變成字典序。
- **AgGrid 的 cellRenderer 不能回傳 DOM 節點**（React error #31，整個元件會掛掉）。要畫東西就用 `cellStyle`（占比長條用 CSS 漸層）或在 Python 端轉成 CSS（表格裡的走勢長條是多重 linear-gradient，見 `theme.spark_css()`）。
- **`data_return_mode` 不能設 `MINIMAL`** —— 那會連 `selected_rows` 一起省掉，表格看起來選中了，Python 端卻永遠收到空的。
- **每個欄位都要有 minWidth**，否則側欄展開或視窗變窄時欄位會被壓成兩三個字寬。
- **全域 CSS 不要整個藏 `[data-testid="stToolbar"]`**：展開 sidebar 的按鈕在裡面，藏掉之後 sidebar 一收合就再也打不開，而收合狀態還會被 localStorage 記住。
- **sidebar 寬度改了要同步改收合位移**（`theme.py` 的 `SIDEBAR_W`），否則收起來會有一條露在畫面上。

## 資料源
Google Sheet `1s9jcoN4wVcKb2aOTAoIUe3Gw-EjbOomnNfvPzA3sJ6o` 的 `*_raw` 分頁。
