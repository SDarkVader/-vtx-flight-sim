@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 or newer with the Windows Python launcher is required.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -c "import mujoco, fastapi, uvicorn, numpy, scipy" >nul 2>&1
if errorlevel 1 (
  echo Installing simulator dependencies. This may take several minutes.
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
echo Starting the VTX simulator. Keep this window open.
.venv\Scripts\python.exe scripts\launch_unified.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo The simulator could not start. Read the error above.
pause
exit /b 1
