@echo off
setlocal
cd /d "%~dp0"
set "PY=D:\Trae-CN\tools\python\python.exe"
echo [1/2] Saving API key...
echo.
"%PY%" scripts\set_key.py
echo.
echo [2/2] Smoke test...
echo.
"%PY%" scripts\smoke_ark.py
echo.
echo Finished. Press any key to close this window.
pause >nul
