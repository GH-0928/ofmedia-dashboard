# dev/ — 開發用工具

這兩支工具讓你**不需要 Google Sheet 憑證與登入密碼**，就能驗證改動。
它們只在本機開發時用，不影響雲端部署（Streamlit Cloud 只跑根目錄的 `app.py`）。

作法都是同一招：在 `app.py` 匯入之前，把會連外的三個模組
（`data` / `calendar_store` / `calendar_view`）換成假的，再跑真正的 `app.py`。
所以你看到的版面、互動、圖表全是真的，只有數字是造出來的。

## test_analysis.py — 歸因計算測試

```bash
python dev/test_analysis.py
```

驗 `analysis.py` 的數字，不碰畫面。最重要的一條是**各項目的變化加總＝整體變化**
—— 這條不成立的話，歸因表上的貢獻度就是騙人的，而這種錯誤在畫面上看不出來。
另外涵蓋：基準期不足 7 天時用實際天數平均、新項目（基準為 0）不能算出無限大的
百分比、小數字的大百分比要被絕對量下限擋掉、花費驟減抓得到。

## smoke_test.py — 離線煙霧測試

```bash
python dev/smoke_test.py
```

用 Streamlit 的 `AppTest` 把整個 app 跑過 23 個情境，檢查有沒有例外：
四個分頁、各種篩選組合、單日期間、六個媒體深度、Meta 三層下鑽、
行事曆分頁、篩到空資料、選取後的三條分支（選 1 列／3 列／6 列）、兩種快篩。

**改完 UI 一定要跑這支。** 它抓得到 column 設定錯誤、欄位改名沒同步、
空資料沒防護這類問題 —— 這些在瀏覽器裡可能要點很多下才會遇到。

一個限制：`AppTest` 沒有前端，AgGrid 永遠回傳「沒有選取」，所以測試裡把
`grid.data_grid` 換成假的（依 `FAKE_SEL` 回傳前 n 列），才測得到選取之後
的路徑。**視覺與實際點擊仍然要靠下面那支。**

## preview_app.py — 假資料預覽

```bash
streamlit run dev/preview_app.py --server.port 8599
```

用亂數假資料跑真正的 `app.py`，跳過密碼登入。裡面刻意製造了三種異常
（Meta 成本惡化、TikTok 量崩、預算集中），讓「異常警示」與快篩
「需要注意」有東西可看。

視覺類的改動（間距、顏色、欄寬、截斷、響應式）只能用這支確認，
`smoke_test.py` 看不出來。

## 注意

- 這兩支的數字都是亂數，**不要拿來核對真實成效**。
- 要用真實資料就放一份 `.streamlit/secrets.toml`（已在 `.gitignore`）
  直接跑 `streamlit run app.py`，或部署到 Streamlit Cloud 看。
