$ErrorActionPreference='Continue'
Set-Location 'C:\Users\steve\Projects\VTX\simulator'
$run='20261101T151650-a47d96'
for($i=0;$i -lt 20;$i++){
  Start-Sleep -Seconds 120
  try{
    git add -- evidence/raymond-flight-two/observations.jsonl evidence/raymond-flight-two/view_snapshots.jsonl evidence/raymond-flight-two/heartbeat.json evidence/raymond-flight-two/errors.jsonl evidence/raymond-flight-two/completed.txt 2>$null
    git add -- "evidence/flights/$run/metadata.json" "evidence/flights/$run/pilot-before.json" 2>$null
    $st=git diff --cached --name-only
    if($st){git commit -m "evidence: Flight Two instrument snapshots batch $i"; git push origin HEAD:fix/mobile-flight-view-performance}
    "$(Get-Date -Format o) batch $i : $st" | Add-Content 'evidence/raymond-flight-two/sync-status.log'
  }catch{$_.Exception.Message | Add-Content 'evidence/raymond-flight-two/sync-status.log'}
}

