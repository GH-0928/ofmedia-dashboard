# -*- coding: utf-8 -*-
"""簡易密碼登入閘。密碼存在 st.secrets['auth']['password']。"""
import streamlit as st

import theme


def require_password() -> None:
    if st.session_state.get("authed"):
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
