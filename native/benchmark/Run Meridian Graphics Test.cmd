@echo off
"%~dp0VTX Native Flight.exe" --display-driver windows --rendering-driver vulkan --rendering-method mobile --resolution 1920x1080 -- --meridian-benchmark
if errorlevel 1 (
  echo The Meridian graphics test exited with an error.
  echo Check "%LOCALAPPDATA%\VTX Meridian Graphics" for the receipt.
  pause
)
