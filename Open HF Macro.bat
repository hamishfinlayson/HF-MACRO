@echo off
title HF Macro
REM Double-click this file to open HF Macro.
cd /d "%~dp0"
echo Starting HF Macro from %CD%
where py >nul 2>nul
if %errorlevel%==0 (
    py -m streamlit run app.py --server.port 8600
) else (
    python -m streamlit run app.py --server.port 8600
)
pause
