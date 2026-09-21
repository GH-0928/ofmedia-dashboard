# -*- coding: utf-8 -*-
"""Google Sheet 資料載入 ── OFmedia 廣告儀表板。

讀 6 個 _raw 分頁(ASA / Meta / Google / TikTok / Applovin / Moloco),
統合成共通欄位的 DataFrame 給 dashboard 用。
"""
import os
import socket
import ssl
import time
from typing import Optional

import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SHEET_ID = "1s9jcoN4wVcKb2aOTAoIUe3Gw-EjbOomnNfvPzA3sJ6o"

# 6 個 _raw 分頁與它們提供的欄位範圍(由我們已知的 schema 整理)
RAW_TABS = {
    "Meta": {
        "tab": "Meta_raw",
        "range": "A:V",
        "common": {
            "date": "date", "media": "media", "os": "os", "country": "country",
            "campaign": "campaign", "spend": "spend",
            "impressions": "impressions", "clicks": "clicks", "installs": "installs",
        },
        "extra": ["ad_group", "ad", "成果 ROAS", "購買次數", "購買轉換值"],
    },
    "ASA": {
        "tab": "ASA_raw",
        "range": "A:V",
        "common": {
            "date": "date", "media": "media", "os": "os", "country": "country",
            "campaign": "campaign", "spend": "spend",
            "impressions": "impressions", "clicks": "clicks", "installs": "installs",
        },
        "extra": ["keyword", "search_term", "match_type", "match_source",
                  "max_cpc_bid", "status", "daily_budget"],
    },
    "Google": {
        "tab": "Google_raw",
        "range": "A:M",
        "common": {
            "date": "date", "media": "media", "os": "os", "country": "country",
            "campaign": "campaign", "spend": "spend",
            "impressions": "impressions", "clicks": "clicks", "installs": "installs",
        },
        "extra": ["ad_group", "network"],
    },
    "TikTok": {
        "tab": "TikTok_raw",
        "range": "A:I",
        "common": {
            "date": "date", "media": "media", "os": "os", "country": "country",
            "campaign": "campaign", "spend": "spend",
            "impressions": "impressions", "clicks": "clicks", "installs": "installs",
        },
        "extra": [],
    },
    "Applovin": {
        "tab": "Applovin_raw",
        "range": "A:I",
        "common": {
            "date": "date", "media": "media", "os": "os", "country": "country",
            "campaign": "campaign", "spend": "spend",
            "impressions": "impressions", "clicks": "clicks", "installs": "installs",
        },
        "extra": [],
    },
    "Moloco": {
        "tab": "Moloco_raw",
        "range": "A:I",
        "common": {
            "date": "date", "media": "media", "os": "os", "country": "country",
            "campaign": "campaign", "spend": "spend",
            "impressions": "impressions", "clicks": "clicks", "installs": "installs",
        },
        "extra": [],
    },
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


# 本機執行時退回既有的 OAuth 使用者 token（與 media_daily 同一份）。
# 依序找這幾個位置，找到哪個算哪個。
LOCAL_TOKEN_CANDIDATES = [
    os.environ.get("OFMEDIA_SHEET_TOKEN", ""),
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "Auto_Claude", "OceanFishooter",
                 "dashboard_sheet", "sheet_token.json"),
    os.path.expanduser(
        r"~/Desktop/Auto_Claude/OceanFishooter/dashboard_sheet/sheet_token.json"),
]


def _local_token_path() -> str:
    for path in LOCAL_TOKEN_CANDIDATES:
        if path and os.path.exists(path):
            return os.path.abspath(path)
    return ""


def _get_credentials():
    """雲端用 service account，本機退回 OAuth 使用者 token。

    雲端的 secrets 一定有 gcp_service_account，走第一條；本機沒有 secrets
    檔案時，存取 st.secrets 會直接丟例外，所以要包起來再往下退。
    """
    try:
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        pass

    token_path = _local_token_path()
    if not token_path:
        raise FileNotFoundError(
            "找不到憑證。雲端請設 st.secrets['gcp_service_account']；"
            "本機請確認 dashboard_sheet/sheet_token.json 存在，"
            "或用環境變數 OFMEDIA_SHEET_TOKEN 指定它的位置。")

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials as UserCredentials

    # 不指定 scopes：沿用 token 自己帶的授權範圍，否則會與既有 token 對不上
    creds = UserCredentials.from_authorized_user_file(token_path)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # refresh 後把新的 access token 寫回去，下次啟動就不用再換一次
        try:
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except OSError:
            pass
    return creds


@st.cache_resource
def _sheets_service():
    return build("sheets", "v4", credentials=_get_credentials(), cache_discovery=False)


# service 物件底下綁著 httplib2 的長連線 socket。雲端 app 閒置一段時間後
# Google 那端會把連線關掉,再用同一個 service 就噴 [Errno 32] Broken pipe。
# 因此讀取失敗時要「丟掉快取的 service、重建連線」再重試,不能只重呼叫一次。
_MAX_RETRY = 3


def _is_retryable(e: Exception) -> bool:
    """判斷是不是「重試就會好」的連線層/暫時性錯誤(非權限或分頁不存在)。"""
    if isinstance(e, HttpError):
        status = getattr(getattr(e, "resp", None), "status", None)
        return status in (429, 500, 502, 503, 504)
    # BrokenPipeError / ConnectionReset / socket.timeout / ssl 錯誤都屬 OSError 家族
    return isinstance(e, (OSError, ssl.SSLError, socket.timeout, TimeoutError))


def _read_tab(tab: str, rng: str) -> pd.DataFrame:
    last_err: Optional[Exception] = None
    for attempt in range(_MAX_RETRY):
        try:
            svc = _sheets_service()
            result = svc.spreadsheets().values().get(
                spreadsheetId=SHEET_ID,
                range=f"{tab}!{rng}",
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="FORMATTED_STRING",
            ).execute()
            values = result.get("values", [])
            if not values:
                return pd.DataFrame()
            header, rows = values[0], values[1:]
            return pd.DataFrame(rows, columns=header)
        except Exception as e:  # noqa: BLE001 - 需分類後決定重試或往外拋
            if not _is_retryable(e) or attempt == _MAX_RETRY - 1:
                raise
            last_err = e
            _sheets_service.clear()      # 關鍵:清掉壞掉的連線,下輪重建
            time.sleep(0.6 * (attempt + 1))
    raise last_err  # pragma: no cover - 迴圈內必定 return 或 raise


def _normalize(df: pd.DataFrame, mapping: dict, media_name: str) -> pd.DataFrame:
    """把單一 raw 表清成共通欄位:date/media/os/country/campaign/spend/imp/clicks/installs。"""
    if df.empty:
        return df
    out = pd.DataFrame()
    for std_col, src_col in mapping.items():
        out[std_col] = df.get(src_col, None)
    # media 欄位若為空就用我們指定的
    if "media" not in out.columns or out["media"].isna().all():
        out["media"] = media_name
    # 把 NaN 的 media 補上
    out["media"] = out["media"].fillna(media_name).replace("", media_name)
    # 轉型
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ["spend", "impressions", "clicks", "installs"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
    # 過濾掉沒日期的列(可能是空白或標題)
    out = out.dropna(subset=["date"])
    # 國家空白用 "—" 代替
    out["country"] = out["country"].fillna("—").replace("", "—").astype(str)
    out["os"] = out["os"].fillna("—").replace("", "—").astype(str)
    out["campaign"] = out["campaign"].fillna("(未命名)").replace("", "(未命名)").astype(str)
    return out


@st.cache_data(ttl=600)
def load_unified() -> pd.DataFrame:
    """讀全部 6 個 _raw,清成共通欄位後合併。

    某個分頁讀失敗時不會整個中斷,但會把「缺了哪幾家媒體」記在
    df.attrs["failed_tabs"],由 app.py 在畫面上明確示警 ──
    否則畫面會拿「少一家媒體」的數字照常算 KPI,看起來正常但會誤導決策。
    """
    frames, failed = [], []
    for media, spec in RAW_TABS.items():
        try:
            raw = _read_tab(spec["tab"], spec["range"])
            cleaned = _normalize(raw, spec["common"], media_name=media)
            frames.append(cleaned)
        except Exception as e:  # noqa: BLE001 - 單一分頁失敗不該拖垮整頁
            failed.append((media, spec["tab"], str(e)))
    if not frames:
        out = pd.DataFrame()
    else:
        out = pd.concat(frames, ignore_index=True)
    out.attrs["failed_tabs"] = failed
    return out


@st.cache_data(ttl=600)
def load_meta_raw() -> pd.DataFrame:
    """Meta_raw 完整版含 ad_group / ad / ROAS,給 Tab 5 用。"""
    df = _read_tab("Meta_raw", "A:V")
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    for c in ["spend", "impressions", "clicks", "installs", "購買次數", "購買轉換值"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    if "成果 ROAS" in df.columns:
        df["成果 ROAS"] = pd.to_numeric(df["成果 ROAS"], errors="coerce")
    df = df.dropna(subset=["date"])
    for c in ["campaign", "ad_group", "ad", "os", "country"]:
        if c in df.columns:
            df[c] = df[c].fillna("(未填)").replace("", "(未填)").astype(str)
    return df


@st.cache_data(ttl=600)
def load_asa_raw() -> pd.DataFrame:
    """ASA_raw 完整版含 keyword/search_term,給 Tab 5 用。"""
    df = _read_tab("ASA_raw", "A:V")
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    for c in ["spend", "impressions", "clicks", "installs", "max_cpc_bid", "daily_budget"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df = df.dropna(subset=["date"])
    for c in ["campaign", "ad_group", "keyword", "search_term",
              "match_type", "match_source", "status"]:
        if c in df.columns:
            df[c] = df[c].fillna("(未填)").replace("", "(未填)").astype(str)
    return df


@st.cache_data(ttl=600)
def load_google_raw() -> pd.DataFrame:
    """Google_raw 完整版含 network,給 Tab 5 用。"""
    df = _read_tab("Google_raw", "A:M")
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    for c in ["spend", "impressions", "clicks", "installs"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df = df.dropna(subset=["date"])
    for c in ["campaign", "ad_group", "network", "os", "country"]:
        if c in df.columns:
            df[c] = df[c].fillna("(未填)").replace("", "(未填)").astype(str)
    return df
