# -*- coding: utf-8 -*-
"""簡易密碼登入閘。密碼存在 st.secrets['auth']['password']。"""
import streamlit as st


def require_password() -> None:
    if st.session_state.get("authed"):
        return

    st.title("🔐 OFmedia 廣告儀表板")
    st.caption("請輸入密碼以繼續")

    pwd = st.text_input("密碼", type="password", key="_pwd_input")
    if st.button("登入"):
        expected = st.secrets.get("auth", {}).get("password")
        if not expected:
            st.error("尚未設定密碼(請在 Streamlit Cloud Secrets 中設定 auth.password)")
            st.stop()
        if pwd == expected:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("密碼錯誤")
    st.stop()
