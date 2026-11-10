param(
    [int]$Port = 18911,
    [string]$DataRoot = '',
    [switch]$Clean
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = 'C:\Users\steve\Documents\Github\-vtx-flight-sim\.venv\Scripts\python.exe'
if (-not $DataRoot) {
    $DataRoot = if ($env:VTX_DATA_ROOT) { $env:VTX_DATA_ROOT } else { 'C:\Users\steve\Projects\vtx-three-panel-data-20261110' }
}
if ($Clean -and (Test-Path -LiteralPath $DataRoot)) {
    Remove-Item -LiteralPath $DataRoot -Recurse -Force
}
if (-not (Test-Path -LiteralPath $python)) { throw "Python environment not found: $python" }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) { throw "Port $Port is already occupied; pass another free -Port." }
New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
Push-Location $repo
try {
    $env:PYTHONPATH = Join-Path $repo 'src'
    $env:VTX_DATA_ROOT = $DataRoot
    Write-Host "VTX development runtime: http://127.0.0.1:$Port/"
    Write-Host "Data: $DataRoot"
    & $python -m uvicorn vtx.dashboard_site:app --host 127.0.0.1 --port $Port
} finally {
    Pop-Location
}

