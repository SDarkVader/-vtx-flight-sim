@echo off
setlocal
title VTX - PR 61 Vehicle Testing
set "VTX_TEST_DIR=%~dp0"
cd /d "%VTX_TEST_DIR%"
if not defined VTX_PYTHON set "VTX_PYTHON=%VTX_TEST_DIR%.venv\Scripts\python.exe"
if not exist "%VTX_PYTHON%" if exist "%USERPROFILE%\Documents\Github\-vtx-flight-sim\.venv\Scripts\python.exe" set "VTX_PYTHON=%USERPROFILE%\Documents\Github\-vtx-flight-sim\.venv\Scripts\python.exe"
if not exist "%VTX_PYTHON%" (
  echo Python environment not found. Run the project setup first.
  goto failed
)
if not defined LOCALAPPDATA (
  echo LOCALAPPDATA is unavailable. Cannot choose a separate test save folder.
  goto failed
)
set "VTX_DATA_ROOT=%LOCALAPPDATA%\VTX\vehicle-tests\pr61"
"%VTX_PYTHON%" tools\check_reviewed_runtime.py
if errorlevel 1 goto failed
if /i "%~1"=="--check" (
  echo Vehicle test build verified. No server or flight started.
  echo Game address: http://127.0.0.1:8781/
  echo Separate test saves: "%VTX_DATA_ROOT%"
  exit /b 0
)
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8781 -State Listen -ErrorAction SilentlyContinue) { exit 1 }"
if errorlevel 1 (
  "%VTX_PYTHON%" scripts\check_airport_server.py --port 8781
  if errorlevel 1 goto failed
  echo This test build is already running. Reuse http://127.0.0.1:8781/
  if not defined VTX_LAUNCHER_NO_PAUSE pause
  exit /b 0
)
set "VTX_TEST_BROWSER="
if /i "%~1"=="--no-browser" set "VTX_TEST_BROWSER=--no-browser"
echo Starting the PR 61 vehicle test build from "%VTX_TEST_DIR%".
echo Game address: http://127.0.0.1:8781/
echo Separate test saves: "%VTX_DATA_ROOT%"
echo Keep this window open while playing. Ctrl+C stops this test server.
"%VTX_PYTHON%" scripts\launch_unified.py --port 8781 --data-root "%VTX_DATA_ROOT%" %VTX_TEST_BROWSER%
if errorlevel 1 goto failed
exit /b 0
:failed
echo Vehicle test server could not start. The existing game has not been replaced.
if not defined VTX_LAUNCHER_NO_PAUSE pause
exit /b 1
