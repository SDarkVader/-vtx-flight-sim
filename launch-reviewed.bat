@echo off
setlocal
cd /d "%~dp0"
if not "%~1"=="" if /i not "%~1"=="--check" (
  echo Supported option: --check
  goto failed
)
if not defined VTX_PYTHON set "VTX_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%VTX_PYTHON%" (
  echo Set VTX_PYTHON to the reviewed environment's python.exe.
  goto failed
)
if not defined VTX_DATA_ROOT (
  echo Set VTX_DATA_ROOT to the existing flight data directory. No new archive is selected automatically.
  goto failed
)
if not exist "%VTX_DATA_ROOT%\." (
  echo VTX_DATA_ROOT does not exist: "%VTX_DATA_ROOT%"
  goto failed
)
"%VTX_PYTHON%" -c "import mujoco, fastapi, uvicorn, numpy" >nul 2>&1
if errorlevel 1 goto failed
"%VTX_PYTHON%" tools\check_reviewed_runtime.py
if errorlevel 1 goto failed
echo Source: "%CD%"
echo Flight data: "%VTX_DATA_ROOT%"
echo Cockpit: http://127.0.0.1:8770/
if /i "%~1"=="--check" (
  echo Configuration verified. No server started.
  exit /b 0
)
echo Keep this window open. Reuse one cockpit tab at the address above.
"%VTX_PYTHON%" scripts\launch_unified.py --port 8770 --data-root "%VTX_DATA_ROOT%" --no-browser
if errorlevel 1 goto failed
exit /b 0
:failed
echo VTX did not start. If port 8770 is busy, use the existing server; this launcher never stops it or chooses another port.
if not defined VTX_LAUNCHER_NO_PAUSE pause
exit /b 1
