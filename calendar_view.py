# -*- coding: utf-8 -*-
"""行事曆／待辦分頁 UI。月曆用 Streamlit 原生自繪（不依賴第三方元件）。"""
import html
import calendar as pycal
from datetime import datetime, date, time as dtime
from zoneinfo import ZoneInfo

import streamlit as st

import calendar_store as gs

CATS = ["工作", "會議", "廣告", "素材", "其他"]
CAT_COLOR = {
    "工作": "#3b82f6", "會議": "#8b5cf6", "廣告": "#ef4444",
    "素材": "#f59e0b", "其他": "#6b7280",
}
PRIORITIES = ["高", "一般", "低"]
WEEK_LABELS = ["日", "一", "二", "三", "四", "五", "六"]

# 雲端伺服器時區為 UTC，用台北時區判斷「今天」，否則深夜會差一天。
TW_TZ = ZoneInfo("Asia/Taipei")


def _today() -> date:
    return datetime.now(TW_TZ).date()


def _iso(d: date, t: dtime | None, allday: bool) -> str:
    if not d:
        return ""
    if allday or t is None:
        return d.isoformat()
    return f"{d.isoformat()}T{t.strftime('%H:%M')}"


def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def _parse_time(s: str) -> dtime | None:
    if not s or "T" not in s:
        return None
    try:
        return datetime.fromisoformat(s).time()
    except ValueError:
        return None


def _render_calendar():
    try:
        events = gs.list_events()
    except Exception as e:
        st.error(f"讀取行事曆失敗：{e}")
        return

    by_day: dict[str, list] = {}
    for e in events:
        key = (e.get("start", "") or "")[:10]
        if key:
            by_day.setdefault(key, []).append(e)

    today = _today()
    if "cal_ym" not in st.session_state:
        st.session_state.cal_ym = (today.year, today.month)
    if "sel_date" not in st.session_state:
        st.session_state.sel_date = today.isoformat()
    cy, cm = st.session_state.cal_ym

    n1, n2, n3, _sp, n_title = st.columns([1, 1, 1, 0.5, 5])
    if n1.button("◀", use_container_width=True):
        st.session_state.cal_ym = (cy - 1, 12) if cm == 1 else (cy, cm - 1)
        st.rerun()
    if n2.button("今天", use_container_width=True):
        st.session_state.cal_ym = (today.year, today.month)
        st.session_state.sel_date = today.isoformat()
        st.rerun()
    if n3.button("▶", use_container_width=True):
        st.session_state.cal_ym = (cy + 1, 1) if cm == 12 else (cy, cm + 1)
        st.rerun()
    n_title.markdown(f"### {cy} 年 {cm} 月")

    hcols = st.columns(7)
    for i, lab in enumerate(WEEK_LABELS):
        hcols[i].markdown(
            f"<div style='text-align:center;font-weight:700;color:#94a3b8;'>{lab}</div>",
            unsafe_allow_html=True)

    weeks = pycal.Calendar(firstweekday=6).monthdatescalendar(cy, cm)
    sel = _parse_date(st.session_state.sel_date)
    for week in weeks:
        cols = st.columns(7)
        for i, d in enumerate(week):
            with cols[i]:
                in_month = (d.month == cm)
                iso = d.isoformat()
                day_evs = by_day.get(iso, [])
                label = f"● {d.day}" if d == today else f"{d.day}"
                btn_type = "primary" if d == sel else "secondary"
                if st.button(label, key=f"day_{iso}", use_container_width=True,
                             type=btn_type, disabled=not in_month):
                    st.session_state.sel_date = iso
                    st.rerun()
                for ev in day_evs[:3]:
                    color = CAT_COLOR.get(ev.get("cat", ""), "#3b82f6")
                    title = html.escape((ev.get("title", "") or "")[:8])
                    st.markdown(
                        f"<div style='font-size:.62rem;line-height:1.3;color:{color};"
                        f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>"
                        f"●{title}</div>", unsafe_allow_html=True)
                if len(day_evs) > 3:
                    st.markdown(
                        f"<div style='font-size:.6rem;color:#94a3b8;'>+{len(day_evs)-3}</div>",
                        unsafe_allow_html=True)

    st.divider()

    sel_iso = st.session_state.sel_date
    st.markdown(f"#### 📅 {sel_iso} 的事件")
    day_events = by_day.get(sel_iso, [])
    if not day_events:
        st.caption("這天沒有事件。")
    for ev in day_events:
        trange = ev.get("start", "")[11:16] if "T" in ev.get("start", "") else "整天"
        with st.expander(f"　{ev.get('title','(無標題)')}　·　{trange}"):
            with st.form(f"edit_ev_{ev['id']}"):
                title = st.text_input("行程名稱", value=ev.get("title", ""))
                cat = st.selectbox("分類", CATS,
                                   index=CATS.index(ev["cat"]) if ev.get("cat") in CATS else 0)
                allday = st.checkbox("整天", value=ev.get("allday") == "1")
                c1, c2 = st.columns(2)
                sd = c1.date_input("起始日期", value=_parse_date(ev.get("start", "")) or today)
                stime = c2.time_input("起始時間",
                                      value=_parse_time(ev.get("start", "")) or dtime(9, 0),
                                      disabled=allday)
                c3, c4 = st.columns(2)
                ed = c3.date_input("結束日期", value=_parse_date(ev.get("end", "")) or today)
                etime = c4.time_input("結束時間",
                                      value=_parse_time(ev.get("end", "")) or dtime(10, 0),
                                      disabled=allday)
                hours = st.text_input("工時（小時）", value=ev.get("hours", ""))
                note = st.text_area("備註", value=ev.get("note", ""), height=70)
                b1, b2 = st.columns(2)
                if b1.form_submit_button("儲存", type="primary"):
                    gs.update_event(ev["id"], title=title.strip(), cat=cat,
                                    allday="1" if allday else "0",
                                    start=_iso(sd, stime, allday), end=_iso(ed, etime, allday),
                                    hours=hours.strip(), note=note.strip())
                    st.rerun()
                if b2.form_submit_button("🗑 刪除"):
                    gs.delete_event(ev["id"])
                    st.rerun()

    with st.expander("➕ 新增事件"):
        with st.form("add_event_form", clear_on_submit=True):
            default_d = _parse_date(sel_iso) or today
            c1, c2 = st.columns(2)
            title = c1.text_input("行程名稱")
            cat = c2.selectbox("分類", CATS, key="add_ev_cat")
            allday = st.checkbox("整天（跨日或全天）", key="add_ev_allday")
            c3, c4 = st.columns(2)
            sd = c3.date_input("起始日期", value=default_d)
            stime = c4.time_input("起始時間", value=dtime(9, 0), disabled=allday)
            c5, c6 = st.columns(2)
            ed = c5.date_input("結束日期", value=default_d)
            etime = c6.time_input("結束時間", value=dtime(10, 0), disabled=allday)
            hours = st.text_input("工時（小時，選填）")
            note = st.text_area("備註", height=70)
            if st.form_submit_button("新增", type="primary"):
                if not title.strip():
                    st.warning("請填行程名稱")
                else:
                    gs.add_event(title=title.strip(), cat=cat, allday=allday,
                                 start=_iso(sd, stime, allday), end=_iso(ed, etime, allday),
                                 hours=hours.strip(), note=note.strip())
                    st.success("已新增")
                    st.rerun()


def _render_todos():
    try:
        todos = gs.list_todos()
    except Exception as e:
        st.error(f"讀取待辦失敗：{e}")
        return

    with st.expander("➕ 新增待辦", expanded=not todos):
        with st.form("add_todo_form", clear_on_submit=True):
            text = st.text_input("待辦內容")
            c1, c2 = st.columns(2)
            priority = c1.selectbox("優先級", PRIORITIES, index=1)
            cat = c2.selectbox("分類", CATS)
            c3, c4 = st.columns(2)
            due = c3.date_input("截止日期", value=_today())
            no_due = c4.checkbox("無截止日")
            note = st.text_area("備註", height=70)
            if st.form_submit_button("新增", type="primary"):
                if not text.strip():
                    st.warning("請填待辦內容")
                else:
                    gs.add_todo(text=text.strip(), priority=priority, cat=cat,
                                due="" if no_due else due.isoformat(),
                                allday=True, note=note.strip())
                    st.success("已新增")
                    st.rerun()

    st.divider()

    if not todos:
        st.info("目前沒有待辦。")
        return

    prio_rank = {"高": 0, "一般": 1, "低": 2}
    todos.sort(key=lambda t: (t.get("done") == "1",
                              prio_rank.get(t.get("priority", "一般"), 1),
                              t.get("due", "")))
    for t in todos:
        done = t.get("done") == "1"
        c0, c1, c2 = st.columns([0.08, 0.82, 0.10])
        checked = c0.checkbox("完成", value=done, key=f"todo_{t['id']}",
                              label_visibility="collapsed")
        if checked != done:
            gs.toggle_todo(t["id"], checked)
            st.rerun()
        dot = CAT_COLOR.get(t.get("cat", ""), "#6b7280")
        label = html.escape(t.get("text", ""))
        meta = []
        if t.get("priority"):
            meta.append(f"優先：{t['priority']}")
        if t.get("due"):
            meta.append(f"截止：{t['due']}")
        if t.get("cat"):
            meta.append(t["cat"])
        meta_str = html.escape("　·　".join(meta))
        style = "color:#64748b;text-decoration:line-through;" if done else ""
        c1.markdown(
            f"<span style='display:inline-block;width:8px;height:8px;border-radius:50%;"
            f"background:{dot};margin-right:6px;'></span>"
            f"<span style='{style}'>{label}</span>"
            f"<br><span style='font-size:.75rem;color:#94a3b8;{style}'>{meta_str}</span>",
            unsafe_allow_html=True)
        if c2.button("🗑", key=f"del_{t['id']}"):
            gs.delete_todo(t["id"])
            st.rerun()


def render():
    sub_cal, sub_todo = st.tabs(["📆 行事曆", "✅ 待辦"])
    with sub_cal:
        _render_calendar()
    with sub_todo:
        _render_todos()
