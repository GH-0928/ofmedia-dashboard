@echo off
REM ============================================================
REM  OFmedia dashboard - local launcher
REM  Runs the real dashboard on this PC with real Google Sheet
REM  data. No password (local mode), no Streamlit Cloud needed.
REM  Close this window to stop the server.
REM ============================================================
setlocal
cd /d "%~dp0"

REM Local mode: skip the password gate (see auth.py local_mode)
set OFMEDIA_LOCAL=1

REM Optional: point to the Google OAuth token explicitly.
REM Leave it commented unless the auto-detected path stops working.
REM set OFMEDIA_SHEET_TOKEN=C:\Users\garyhuang\Desktop\Auto_Claude\OceanFishooter\dashboard_sheet\sheet_token.json

echo Starting OFmedia dashboard on http://localhost:8510 ...
echo (first run may take a few seconds)
start "" http://localhost:8510
python -m streamlit run app.py --server.port 8510 --server.headless true

echo.
echo Server stopped.
pause
