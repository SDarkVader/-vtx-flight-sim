param([string]$RunId,[int]$DurationSeconds=900)
$ErrorActionPreference='Continue'
$root='C:\Users\steve\Projects\VTX\simulator'
$folder=Join-Path $root "evidence\flights\$RunId"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$path=Join-Path $folder 'raymond-monitor.jsonl'
$end=(Get-Date).AddSeconds($DurationSeconds)
while((Get-Date) -lt $end) {
  try {
    $v=Invoke-RestMethod 'http://127.0.0.1:8765/api/observe' -TimeoutSec 5
    $row=[ordered]@{wall_utc=(Get-Date).ToUniversalTime().ToString('o');run_id=$RunId;kind='pilot_observation';data=$v}
    ($row | ConvertTo-Json -Depth 15 -Compress) | Add-Content -Path $path -Encoding UTF8
    if(-not $v.active) {break}
  } catch {
    $row=[ordered]@{wall_utc=(Get-Date).ToUniversalTime().ToString('o');kind='recorder_error';message=$_.Exception.Message}
    ($row | ConvertTo-Json -Compress) | Add-Content -Path $path -Encoding UTF8
  }
  Start-Sleep -Seconds 1
}
