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
| 投放總覽 | 八個 KPI（規模四個、效率四個，含對比期變化與近 7 天走勢）、異常警示、每日趨勢（含廣告操作標記）、媒體分布、期間內操作紀錄 |
| 媒體對比 | 六媒體並排對比表（花費占比畫成長條）、CPI 排行 |
| 地區・OS | iOS 與 Android 對照、國家表現前 15 名、國家 × 媒體 CPI 熱力圖 |
| 媒體深度 | Meta 三層下鑽（Campaign → Ad Group → 素材）、ASA 關鍵字與搜尋詞、Google Network 與 Ad Group，其餘媒體看 Campaign 排行 |

## 檔案

| 檔案 | 用途 |
|---|---|
| `app.py` | 主程式：資料篩選、各分頁的圖表與表格 |
| `theme.py` | **視覺系統的唯一來源**：色階、間距、字級、圖表主題、表格欄位格式、共用 HTML 元件 |
| `data.py` | Google Sheet 讀取與欄位統合 |
| `auth.py` | 密碼登入閘 |
| `calendar_view.py` / `calendar_store.py` | 行事曆・待辦 |
| `.streamlit/config.toml` | Streamlit 原生元件的主題色 |

## 維護須知

- **改外觀先看 `theme.py`。** `app.py` 裡不寫 hex 色碼，一律引用 token；`config.toml` 的主題色要跟 `theme.py` 同步，否則原生元件（表格、輸入框）會和自訂卡片不同色系。
- **表格欄位保留數值型別**，格式化交給 `theme.money_col()`、`cost_col()`、`pct_col()` 這些 helper。若先把數字轉成 `"$1,234"` 字串再丟進 `st.dataframe`，點欄位排序會變成字典序。
- **全域 CSS 不要整個藏 `[data-testid="stToolbar"]`**：展開 sidebar 的按鈕在裡面，藏掉之後 sidebar 一收合就再也打不開，而收合狀態還會被 localStorage 記住。
- **sidebar 寬度改了要同步改收合位移**（`theme.py` 的 `SIDEBAR_W`），否則收起來會有一條露在畫面上。

## 資料源
Google Sheet `1s9jcoN4wVcKb2aOTAoIUe3Gw-EjbOomnNfvPzA3sJ6o` 的 `*_raw` 分頁。
