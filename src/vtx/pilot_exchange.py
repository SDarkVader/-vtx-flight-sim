"""Passive audit recorder for model exchanges made by an external AI pilot.

The simulator does not see the model API request or raw response. The caller
must invoke this at its own model boundary; no flight-control hooks are changed.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

_SECRET = re.compile(r'(api[_-]?key|authorization|access[_-]?token|secret|password|cookie)', re.I)

def _redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if _SECRET.search(k) else _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def record_exchange(data_root: str | Path, *, flight_id: str, decision_id: str,
                    request_payload: object, response_payload: object,
                    observation_id: int | None = None, sim_time_s: float | None = None,
                    raw_request_sha256: str | None = None,
                    raw_response_sha256: str | None = None) -> Path:
    """Persist one decision without overwriting an existing record.

    The caller supplies actual API payloads, not reconstructed simulator data.
    Sensitive object fields are redacted, so saved JSON is not byte-identical.
    Optional hashes can attest to raw bytes without storing those bytes.
    """
    for identifier in (flight_id, decision_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', identifier):
            raise ValueError('Invalid flight or decision ID')
    directory = Path(data_root) / 'evidence' / 'flights' / flight_id / 'pilot-exchanges'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (decision_id + '.json')
    if target.exists():
        raise FileExistsError(decision_id)
    row = dict(schema_version=1, flight_id=flight_id, decision_id=decision_id,
               recorded_utc=datetime.now(timezone.utc).isoformat(),
               observation_id=observation_id, sim_time_s=sim_time_s,
               request_payload=_redact(request_payload),
               response_payload=_redact(response_payload),
               raw_request_sha256=raw_request_sha256,
               raw_response_sha256=raw_response_sha256,
               source='external_model_caller')
    encoded = json.dumps(row, ensure_ascii=False, allow_nan=False,
                         separators=(',', ':')).encode('utf-8')
    temporary = directory / ('.' + decision_id + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)  # atomic create-if-absent
    finally:
        temporary.unlink(missing_ok=True)
    return target
