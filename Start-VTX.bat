@echo off
setlocal
title VTX Game
set "VTX_GAME_DIR=%~dp0"
if not exist "%VTX_GAME_DIR%\scripts\launch_unified.py" (
  echo Game files not found at "%VTX_GAME_DIR%".
  goto failed
)
cd /d "%VTX_GAME_DIR%"
if not defined VTX_PYTHON set "VTX_PYTHON=%VTX_GAME_DIR%.venv\Scripts\python.exe"
if not exist "%VTX_PYTHON%" if exist "%USERPROFILE%\Documents\Github\-vtx-flight-sim\.venv\Scripts\python.exe" set "VTX_PYTHON=%USERPROFILE%\Documents\Github\-vtx-flight-sim\.venv\Scripts\python.exe"
if not exist "%VTX_PYTHON%" (
  echo Python environment not found at "%VTX_PYTHON%".
  goto failed
)
if not defined VTX_DATA_ROOT if exist "%LOCALAPPDATA%\VTX\checkouts\vtx-flight-sim-d1e44131\." set "VTX_DATA_ROOT=%LOCALAPPDATA%\VTX\checkouts\vtx-flight-sim-d1e44131"
if not defined VTX_DATA_ROOT for /f "usebackq delims=" %%D in (`"%VTX_PYTHON%" -c "from scripts.launch_unified import DEFAULT_DATA_ROOT; print(DEFAULT_DATA_ROOT)"`) do set "VTX_DATA_ROOT=%%D"
if not defined VTX_DATA_ROOT goto failed
if not exist "%VTX_DATA_ROOT%\." mkdir "%VTX_DATA_ROOT%"
if not exist "%VTX_DATA_ROOT%\." goto failed
"%VTX_PYTHON%" tools\check_reviewed_runtime.py
if errorlevel 1 goto failed
if /i "%~1"=="--check" exit /b 0
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8770 -State Listen -ErrorAction SilentlyContinue) { exit 1 }"
if errorlevel 1 (
  echo Port 8770 is already in use. Open http://127.0.0.1:8770/ for the existing session.
  goto failed
)
"%VTX_PYTHON%" scripts\prepare_windows_launch.py "%VTX_DATA_ROOT%"
if errorlevel 1 goto failed
echo Starting VTX. Keep this window open while you play.
echo Flight data: "%VTX_DATA_ROOT%"
"%VTX_PYTHON%" scripts\launch_unified.py --port 8770 --data-root "%VTX_DATA_ROOT%"
if errorlevel 1 goto failed
exit /b 0
:failed
echo VTX could not start. See the message above.
if not defined VTX_LAUNCHER_NO_PAUSE pause
exit /b 1
