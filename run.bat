@echo off
rem Double-click this file to start the game server.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
    rem Let this venv import mobilelink from ..\game_common
    powershell -NoProfile -ExecutionPolicy Bypass -File "..\game_common\install.ps1" "%~dp0"
)

.venv\Scripts\python.exe main.py

echo.
echo Server stopped. Press any key to close.
pause > nul
