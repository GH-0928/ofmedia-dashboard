# -*- coding: utf-8 -*-
"""Google Sheet 資料載入 ── OFmedia 廣告儀表板。

讀 6 個 _raw 分頁(ASA / Meta / Google / TikTok / Applovin / Moloco),
統合成共通欄位的 DataFrame 給 dashboard 用。
"""
from typing import Optional

import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

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


def _get_credentials() -> Credentials:
    info = dict(st.secrets["gcp_service_account"])
    return Credentials.from_service_account_info(info, scopes=SCOPES)


@st.cache_resource
def _sheets_service():
    return build("sheets", "v4", credentials=_get_credentials(), cache_discovery=False)


def _read_tab(tab: str, rng: str) -> pd.DataFrame:
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
    df = pd.DataFrame(rows, columns=header)
    return df


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
    """讀全部 6 個 _raw,清成共通欄位後合併。"""
    frames = []
    for media, spec in RAW_TABS.items():
        try:
            raw = _read_tab(spec["tab"], spec["range"])
            cleaned = _normalize(raw, spec["common"], media_name=media)
            frames.append(cleaned)
        except Exception as e:
            st.warning(f"讀 {spec['tab']} 失敗:{e}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


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
