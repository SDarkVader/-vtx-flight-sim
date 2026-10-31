"""Export observed pilot experience without constructing a transfer world."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json

root=Path(__file__).resolve().parents[1]
source=root/'pilot/colin-memory.json'
state=json.loads(source.read_text())
assert state['stage2_accessed'] is False
manifest=dict(schema_version=1,pilot='Colin',created_utc=datetime.now(timezone.utc).isoformat(),
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    state=state,representation='Explicit observed lessons and experience history, not an executable control policy',
    demonstrated_proficiency='No controlled A-to-B landing; retained failure experience',
    environment_access=dict(stage1='VTX valley test range',stage2='NOT CREATED OR ACCESSED'),
    transfer_instructions='Load this state when the proprietor supplies the unfamiliar second environment. Do not train on or inspect that environment in advance.')
(root/'pilot/transfer-checkpoint.json').write_text(json.dumps(manifest,indent=2))
print('Saved',state['experience_count'],'observed lessons; Stage 2 not accessed')
