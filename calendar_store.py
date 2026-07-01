# -*- coding: utf-8 -*-
"""行事曆／待辦資料層：寫進廣告 Sheet 的兩個分頁 calendar_events / todos。

沿用本 app 現有的 service account（st.secrets['gcp_service_account']），
但需要「寫入」scope；廣告資料是唯讀，行事曆要可寫，故獨立一組憑證。
本機開發可用環境變數 OF_LOCAL_TOKEN（OAuth token 路徑）+ OF_CAL_SHEET_ID 覆寫。
"""
import os
import time
import random

import streamlit as st
from googleapiclient.discovery import build

from data import SHEET_ID as AD_SHEET_ID

WRITE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TAB_EVENTS = "calendar_events"
TAB_TODOS = "todos"
TAB_OPS = "ad_ops"

EVENT_COLS = ["id", "title", "cat", "allday", "start", "end", "hours", "note"]
TODO_COLS = ["id", "text", "priority", "cat", "done", "due", "end", "allday", "hours", "note"]
# 廣告操作：date/media 為對照廣告數據的 join key，op_type 為結構化分類（供統計/AI）
OPS_COLS = ["id", "date", "op_type", "media", "campaign", "note"]
TAB_COLS = {TAB_EVENTS: EVENT_COLS, TAB_TODOS: TODO_COLS, TAB_OPS: OPS_COLS}


def _sheet_id() -> str:
    return os.environ.get("OF_CAL_SHEET_ID") or AD_SHEET_ID


def _credentials():
    # 雲端：service account（廣告 app 現成的憑證，改用寫入 scope）
    try:
        if "gcp_service_account" in st.secrets:
            from google.oauth2.service_account import Credentials
            info = dict(st.secrets["gcp_service_account"])
            return Credentials.from_service_account_info(info, scopes=WRITE_SCOPES)
    except Exception:
        pass

    # 本機開發：OAuth 使用者 token（路徑走環境變數，避免耦合到其他 repo）
    local_token = os.environ.get("OF_LOCAL_TOKEN")
    if local_token and os.path.exists(local_token):
        from google.oauth2.credentials import Credentials as UserCreds
        from google.auth.transport.requests import Request
        creds = UserCreds.from_authorized_user_file(local_token, WRITE_SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds

    raise RuntimeError("找不到憑證：雲端需 st.secrets['gcp_service_account']，"
                       "本機需設環境變數 OF_LOCAL_TOKEN。")


@st.cache_resource(show_spinner=False)
def _service():
    return build("sheets", "v4", credentials=_credentials(), cache_discovery=False)


# ──────────────────────────────── 分頁維護 ────────────────────────────────

def _ensure_tabs():
    flag = "_cal_tabs_ready"
    if st.session_state.get(flag):
        return
    svc, sid = _service(), _sheet_id()
    meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
    existing = {s["properties"]["title"] for s in meta["sheets"]}
    add_reqs = [{"addSheet": {"properties": {"title": t}}}
                for t in TAB_COLS if t not in existing]
    if add_reqs:
        svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": add_reqs}).execute()
    for tab, cols in TAB_COLS.items():
        res = svc.spreadsheets().values().get(
            spreadsheetId=sid, range=f"'{tab}'!A1:Z1").execute()
        if not res.get("values"):
            svc.spreadsheets().values().update(
                spreadsheetId=sid, range=f"'{tab}'!A1",
                valueInputOption="RAW", body={"values": [cols]}).execute()
    st.session_state[flag] = True


# ──────────────────────────────── 低階讀寫 ────────────────────────────────

def _read(tab: str) -> list[dict]:
    _ensure_tabs()
    svc, sid = _service(), _sheet_id()
    values = svc.spreadsheets().values().get(
        spreadsheetId=sid, range=f"'{tab}'!A:Z").execute().get("values", [])
    if len(values) < 2:
        return []
    header = values[0]
    return [dict(zip(header, row + [""] * (len(header) - len(row))))
            for row in values[1:]]


def _write_all(tab: str, records: list[dict]):
    # 先寫新資料（含表頭）再清尾巴：不先 clear，避免 update 失敗時整份被清空。
    _ensure_tabs()
    svc, sid = _service(), _sheet_id()
    cols = TAB_COLS[tab]
    values = [cols] + [[str(r.get(c, "")) for c in cols] for r in records]
    svc.spreadsheets().values().update(
        spreadsheetId=sid, range=f"'{tab}'!A1",
        valueInputOption="RAW", body={"values": values}).execute()
    svc.spreadsheets().values().clear(
        spreadsheetId=sid, range=f"'{tab}'!A{len(values) + 1}:Z").execute()


def _new_id() -> str:
    return f"{int(time.time() * 1000)}{random.randint(100, 999)}"


def _update_by_id(tab: str, rid, fields: dict):
    cols = TAB_COLS[tab]
    rows = _read(tab)
    for r in rows:
        if r.get("id") == str(rid):
            r.update({k: v for k, v in fields.items() if k in cols})
    _write_all(tab, rows)


def _delete_by_id(tab: str, rid):
    _write_all(tab, [r for r in _read(tab) if r.get("id") != str(rid)])


# ──────────────────────────────── 行事曆 API ────────────────────────────────

def list_events() -> list[dict]:
    return _read(TAB_EVENTS)


def add_event(title, cat="", allday=False, start="", end="", hours="", note=""):
    rows = _read(TAB_EVENTS)
    rows.append({"id": _new_id(), "title": title, "cat": cat,
                 "allday": "1" if allday else "0",
                 "start": start, "end": end, "hours": hours, "note": note})
    _write_all(TAB_EVENTS, rows)


def update_event(event_id, **fields):
    _update_by_id(TAB_EVENTS, event_id, fields)


def delete_event(event_id):
    _delete_by_id(TAB_EVENTS, event_id)


# ──────────────────────────────── 待辦 API ────────────────────────────────

def list_todos() -> list[dict]:
    return _read(TAB_TODOS)


def add_todo(text, priority="一般", cat="", due="", end="", allday=False, hours="", note=""):
    rows = _read(TAB_TODOS)
    rows.append({"id": _new_id(), "text": text, "priority": priority, "cat": cat,
                 "done": "0", "due": due, "end": end,
                 "allday": "1" if allday else "0", "hours": hours, "note": note})
    _write_all(TAB_TODOS, rows)


def update_todo(todo_id, **fields):
    _update_by_id(TAB_TODOS, todo_id, fields)


def toggle_todo(todo_id, done: bool):
    update_todo(todo_id, done="1" if done else "0")


def delete_todo(todo_id):
    _delete_by_id(TAB_TODOS, todo_id)


# ──────────────────────────────── 廣告操作 API ────────────────────────────────

def list_ops() -> list[dict]:
    return _read(TAB_OPS)


def add_op(date, op_type, media, campaign="", note=""):
    rows = _read(TAB_OPS)
    rows.append({"id": _new_id(), "date": date, "op_type": op_type,
                 "media": media, "campaign": campaign, "note": note})
    _write_all(TAB_OPS, rows)


def update_op(op_id, **fields):
    _update_by_id(TAB_OPS, op_id, fields)


def delete_op(op_id):
    _delete_by_id(TAB_OPS, op_id)
