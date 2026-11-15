@echo off
title HF Macro (PC edition)
REM Double-click this file to open HF Macro on your PC.
cd /d "%~dp0"
echo Starting HF Macro from %CD%
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
echo Checking libraries (first run can take a minute)...
%PY% -m pip install -q -r requirements.txt
%PY% -m streamlit run app.py --server.port 8600
pause
