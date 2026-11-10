param([int]$Port = 18911)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = 'C:\Users\steve\Documents\Github\-vtx-flight-sim\.venv\Scripts\python.exe'
$dataRoot = 'C:\Users\steve\Projects\vtx-three-panel-data-20261110'
if (-not (Test-Path -LiteralPath $python)) { throw "Python environment not found: $python" }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { throw "Port $Port is already occupied; pass another free -Port." }
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
Push-Location $repo
try {
    $env:PYTHONPATH = Join-Path $repo 'src'
    $env:VTX_DATA_ROOT = $dataRoot
    Write-Host "VTX development runtime: http://127.0.0.1:$Port/"
    Write-Host "Data: $dataRoot"
    & $python -m uvicorn vtx.dashboard_site:app --host 127.0.0.1 --port $Port
} finally {
    Pop-Location
}
