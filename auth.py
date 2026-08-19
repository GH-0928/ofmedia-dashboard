# -*- coding: utf-8 -*-
"""簡易密碼登入閘。密碼存在 st.secrets['auth']['password']。"""
import streamlit as st


def require_password() -> None:
    if st.session_state.get("authed"):
        return

    # 置中卡片登入頁
    st.markdown(
        """
        <style>
        /* 這兩條只在登入頁生效:規則綁在登入卡片的 #of-login-page 標記上。
           以前寫成無條件的 [data-testid="stSidebar"]{display:none},登入成功
           rerun 後這段 <style> 若殘留在 DOM(雲端 session 重連時會發生),
           就會把整個左側導覽藏掉 —— Streamlit 的「收合 sidebar」用的正是
           display:none,所以連展開鈕都不會出現,等於沒有救援出口。
           改成相依選擇器後,登入頁標記一消失規則就自動失效。 */
        body:has(#of-login-page) [data-testid="stSidebar"] {display: none;}
        body:has(#of-login-page) .block-container {max-width: 460px; padding-top: 8vh;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div id="of-login-page" style="
            background: linear-gradient(135deg, #1E3A5F 0%, #1E293B 100%);
            border: 1px solid #25406B; border-radius: 18px;
            padding: 34px 30px 26px; margin-bottom: 22px; text-align: center;
            box-shadow: 0 8px 28px rgba(0,0,0,0.35);
        ">
            <div style="font-size: 52px; line-height: 1;">🌊</div>
            <div style="font-size: 22px; font-weight: 800; color: #F8FAFC;
                        margin-top: 10px; letter-spacing: -0.4px;">
                Ocean Fishooter
            </div>
            <div style="font-size: 14px; color: #94A3B8; margin-top: 2px;">
                廣告投放儀表板
            </div>
            <div style="font-size: 12.5px; color: #64748B; margin-top: 14px;">
                🔐 請輸入密碼以繼續
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pwd = st.text_input("密碼", type="password", key="_pwd_input",
                        label_visibility="collapsed", placeholder="輸入密碼…")
    if st.button("登入", use_container_width=True, type="primary"):
        expected = st.secrets.get("auth", {}).get("password")
        if not expected:
            st.error("尚未設定密碼(請在 Secrets 中設定 auth.password)")
            st.stop()
        if pwd == expected:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("密碼錯誤")
    st.stop()
