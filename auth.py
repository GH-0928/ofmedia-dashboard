# -*- coding: utf-8 -*-
"""簡易密碼登入閘。密碼存在 st.secrets['auth']['password']。

本機模式（見 local_mode()）會跳過密碼 —— 那是自己機器上的單人使用，
每次開都要打一次密碼只是阻力。雲端絕不會跳過，條件寫得很保守：
必須「有本機旗標」而且「看不到雲端的 service account」兩者同時成立。
"""
import os

import streamlit as st

import theme

# 放在 repo 根目錄的空檔案，存在就代表本機模式（已列入 .gitignore）
LOCAL_FLAG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               ".local_mode")


def local_mode() -> bool:
    """是否為本機模式。兩個條件都成立才算，少一個就照常要密碼。"""
    flagged = (os.environ.get("OFMEDIA_LOCAL") == "1"
               or os.path.exists(LOCAL_FLAG_FILE))
    if not flagged:
        return False
    # 看得到雲端的 service account 就代表這是雲端（或本機刻意接了雲端憑證），
    # 這種情況一律要密碼，避免旗標被誤帶上線就把儀表板公開出去
    try:
        if "gcp_service_account" in st.secrets:
            return False
    except Exception:
        pass
    return True


def require_password() -> None:
    if st.session_state.get("authed") or local_mode():
        return

    # 這兩條只在登入頁生效：規則綁在登入卡片的 #of-login-page 標記上。
    # 以前寫成無條件的 [data-testid="stSidebar"]{display:none}，登入成功
    # rerun 後這段 <style> 若殘留在 DOM（雲端 session 重連時會發生），
    # 就會把整個左側導覽藏掉 —— Streamlit 的「收合 sidebar」用的正是
    # display:none，所以連展開鈕都不會出現，等於沒有救援出口。
    # 改成相依選擇器後，登入頁標記一消失規則就自動失效。
    st.markdown(
        f"""
        <style>
        body:has(#of-login-page) [data-testid="stSidebar"] {{display: none;}}
        body:has(#of-login-page) .block-container {{
            max-width: 380px; padding-top: 14vh;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div id="of-login-page" style="text-align: center; margin-bottom: 26px;">
            <div style="width: 42px; height: 42px; border-radius: 11px;
                        margin: 0 auto 14px;
                        background: linear-gradient(135deg, {theme.ACCENT} 0%,
                                    {theme.ACCENT_DEEP} 100%);"></div>
            <div style="font-size: 19px; font-weight: 700; color: {theme.TEXT};
                        letter-spacing: -0.3px;">Ocean Fishooter</div>
            <div style="font-size: 13px; color: {theme.TEXT_MID}; margin-top: 3px;">
                廣告投放儀表板</div>
            <div style="font-size: 11.5px; color: {theme.TEXT_DIM}; margin-top: 16px;">
                請輸入密碼以繼續</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pwd = st.text_input("密碼", type="password", key="_pwd_input",
                        label_visibility="collapsed", placeholder="密碼")
    if st.button("登入", width='stretch', type="primary"):
        expected = st.secrets.get("auth", {}).get("password")
        if not expected:
            st.error("尚未設定密碼（請在 Secrets 中設定 auth.password）")
            st.stop()
        if pwd == expected:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("密碼錯誤")
    st.stop()
