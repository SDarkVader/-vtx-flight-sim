"""Isolated, scheduled MuJoCo experiments using the same Laboratory as live flight."""
from __future__ import annotations

import asyncio
import io
import json
import zipfile
import re
import threading
import uuid
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .phantom.experiment_config import build_overrides, parameter_catalogue


class ScheduledAction(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    at_s: float = Field(ge=0, le=120)
    action: dict


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    airframe_variant: str = 'phantom-a10b'
    start_configuration: str = 'road'
    p6_enabled: bool | None = None
    experimental_overrides: dict[str, object] = Field(default_factory=dict, max_length=32)
    departure: list[float] = Field(default_factory=lambda: [0., 0.])
    duration_s: float = Field(default=2, gt=0, le=120)
    max_attitude_deg: float | None = Field(default=None, ge=1, le=90)
    schedule: list[ScheduledAction] = Field(default_factory=list, max_length=100)


def install_experiment_routes(app, get_lab, Laboratory, Mission, parse_action, dt):
    active = {}
    lock = threading.Lock()
    status_lock = threading.RLock()

    def location(experiment_id):
        if not re.fullmatch(r'[0-9a-f]{32}', experiment_id):
            raise HTTPException(422, 'Invalid experiment ID')
        root = get_lab().data_root / 'experiments' / experiment_id
        if not root.is_dir():
            raise HTTPException(404, 'Experiment not found')
        return root

    def write_status(root, state):
        with status_lock:
            path = root / 'status.json'
            tmp = root / 'status.tmp'
            tmp.write_text(json.dumps(state, indent=2), encoding='utf-8')
            tmp.replace(path)

    def read_status(root):
        with status_lock:
            return json.loads((root / 'status.json').read_text(encoding='utf-8'))

    def run(root, spec, cancel):
        state = {'id': root.name, 'status': 'running', 'progress_s': 0.0}
        isolated = None
        try:
            write_status(root, state)
            isolated = Laboratory(data_root=root)
            options = {'start_configuration': spec.start_configuration, 'p6_enabled': spec.p6_enabled,
                       'experimental_overrides': spec.experimental_overrides} if spec.airframe_variant.startswith('phantom') else None
            mission = Mission(airframe_variant=spec.airframe_variant, departure=spec.departure,
                              destination=[-50., 20.], authority='manual', phantom=options,
                              label='Isolated physics experiment')
            result = isolated.start(mission)
            state['run_id'] = result['run_id']
            schedule = sorted(spec.schedule, key=lambda item: item.at_s)
            index = 0
            last_report = -1
            next_abort_check = 0.0
            abort_reason = None
            while isolated.active and isolated.aircraft.data.time < spec.duration_s and not cancel.is_set():
                now = float(isolated.aircraft.data.time)
                while index < len(schedule) and schedule[index].at_s <= now + dt / 2:
                    action = dict(schedule[index].action)
                    action.update(authority='manual', expected_run_id=isolated.run_id,
                                  reason='Scheduled experiment action')
                    if spec.airframe_variant.startswith('phantom'):
                        action['schema'] = 'phantom-fbw-1'
                    isolated.accept_action(parse_action(action))
                    index += 1
                isolated.integrate()
                elapsed = float(isolated.aircraft.data.time)
                if isolated.active and spec.max_attitude_deg is not None and elapsed >= next_abort_check:
                    observation = isolated.sensor_observation()
                    attitude = observation.get('attitude_deg')
                    if isinstance(attitude, dict):
                        angles = [attitude['roll'], attitude['pitch']]
                    else:
                        angles = observation['attitude_xyz_deg'][:2]
                    if max(abs(angle) for angle in angles) >= spec.max_attitude_deg:
                        abort_reason = f'Measured roll or pitch reached {spec.max_attitude_deg} degrees'
                        isolated.log('experiment_abort_condition', dict(reason=abort_reason, attitude_deg=angles))
                        break
                    next_abort_check = elapsed + .1
                if int(elapsed * 2) != last_report:
                    last_report = int(elapsed * 2)
                    state['progress_s'] = round(elapsed, 3)
                    write_status(root, state)
            if isolated.active:
                reason = ('Experiment abort condition: ' + abort_reason if abort_reason else
                          'Experiment aborted by operator' if cancel.is_set() else 'Experiment duration completed')
                isolated.stop(reason)
            outcome = (isolated.end_summary or {}).get('outcome')
            final_status = 'aborted' if cancel.is_set() or abort_reason else ('crashed' if outcome == 'collision' else 'completed')
            state.update(status=final_status, progress_s=round(float(isolated.aircraft.data.time), 3),
                         outcome=outcome, abort_reason=abort_reason)
        except Exception as exc:
            state.update(status='error', error=str(exc))
            if isolated is not None and isolated.active:
                try:
                    isolated.stop('Experiment error; evidence retained')
                except Exception as stop_error:
                    state['error'] += '; evidence finalization failed: ' + str(stop_error)
        finally:
            try:
                write_status(root, state)
            finally:
                with lock:
                    active.pop(root.name, None)

    @app.get('/api/experiment-parameters/{variant}')
    async def experiment_parameters(variant: str):
        try:
            return {'variant': variant, 'parameters': parameter_catalogue(variant)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post('/api/experiments')
    async def create_experiment(spec: ExperimentRequest):
        if spec.experimental_overrides and not spec.airframe_variant.startswith('phantom'):
            raise HTTPException(422, 'Parameter overrides are currently available for Phantom aircraft')
        if spec.p6_enabled is not None and spec.airframe_variant != 'phantom-fx':
            raise HTTPException(422, 'Explicit P6 selection is available for Phantom A10-A')
        if spec.start_configuration not in ('road', 'vtol'):
            raise HTTPException(422, 'Start configuration must be road or vtol')
        if any(item.at_s >= spec.duration_s for item in spec.schedule):
            raise HTTPException(422, 'Scheduled actions must occur before the experiment ends')
        try:
            Mission(airframe_variant=spec.airframe_variant, departure=spec.departure)
            if spec.experimental_overrides:
                build_overrides(spec.airframe_variant, None, spec.experimental_overrides)
            for item in spec.schedule:
                action = dict(item.action)
                action.update(authority='manual', reason='Scheduled experiment action')
                if spec.airframe_variant.startswith('phantom'):
                    action['schema'] = 'phantom-fbw-1'
                parse_action(action)
        except Exception as exc:
            raise HTTPException(422, f'Invalid experiment: {exc}') from exc
        with lock:
            if active:
                raise HTTPException(409, 'An experiment is already running')
            experiment_id = uuid.uuid4().hex
            root = get_lab().data_root / 'experiments' / experiment_id
            root.mkdir(parents=True, exist_ok=False)
            (root / 'request.json').write_text(spec.model_dump_json(indent=2), encoding='utf-8')
            cancel = threading.Event()
            active[experiment_id] = cancel
            write_status(root, {'id': experiment_id, 'status': 'queued', 'progress_s': 0.0})
        asyncio.create_task(asyncio.to_thread(run, root, spec, cancel))
        return {'id': experiment_id, 'status': 'queued'}

    def visible_status(root):
        state = read_status(root)
        with lock:
            running_here = root.name in active
        if state.get('status') in ('queued', 'running') and not running_here:
            state['status'] = 'interrupted'
        request_file = root / 'request.json'
        if request_file.is_file():
            request = json.loads(request_file.read_text(encoding='utf-8'))
            state['airframe_variant'] = request.get('airframe_variant')
            state['p6_enabled'] = request.get('p6_enabled')
        return state

    @app.get('/api/experiments')
    async def list_experiments():
        root = get_lab().data_root / 'experiments'
        if not root.exists():
            return {'experiments': []}
        results = []
        for child in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not child.is_dir() or not re.fullmatch(r'[0-9a-f]{32}', child.name):
                continue
            try:
                results.append(visible_status(child))
            except (OSError, ValueError):
                continue
        return {'experiments': results}

    @app.get('/api/experiments/{experiment_id}')
    async def experiment_status(experiment_id: str):
        return visible_status(location(experiment_id))

    @app.post('/api/experiments/{experiment_id}/abort')
    async def abort_experiment(experiment_id: str):
        location(experiment_id)
        with lock:
            cancel = active.get(experiment_id)
            if cancel is None:
                raise HTTPException(409, 'Experiment is not running')
            cancel.set()
        return {'id': experiment_id, 'abort_requested': True}

    @app.get('/api/experiments/{experiment_id}/export')
    async def export_experiment(experiment_id: str):
        root = location(experiment_id)
        state = visible_status(root)
        if state['status'] in ('queued', 'running'):
            raise HTTPException(409, 'Wait until the experiment has stopped before exporting')
        run_id = state.get('run_id', '')
        if not re.fullmatch(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{6}', run_id):
            raise HTTPException(404, 'Run evidence not available')
        flight = root / 'evidence' / 'flights' / run_id
        allowed = ('metadata.json', 'model.xml', 'summary.json', 'events.jsonl',
                   'phantom_parameters.json', 'phantom_ledger.json', 'phantom_steps.csv.gz',
                   'crash_ring.npz', 'engineering_findings.json')
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for filename in ('request.json', 'status.json'):
                path = root / filename
                if path.is_file():
                    archive.write(path, filename)
            for filename in allowed:
                path = flight / filename
                if path.is_file():
                    archive.write(path, f'evidence/{run_id}/{filename}')
        output.seek(0)
        return StreamingResponse(output, media_type='application/zip',
                                 headers={'Content-Disposition': f'attachment; filename="vtx-experiment-{experiment_id}.zip"'})

    @app.get('/api/experiments/{experiment_id}/files/{name}')
    async def experiment_file(experiment_id: str, name: str):
        if name not in ('request.json', 'summary.json', 'events.jsonl', 'phantom_parameters.json', 'phantom_ledger.json', 'crash_ring.npz'):
            raise HTTPException(404, 'Evidence file not available')
        root = location(experiment_id)
        state = read_status(root)
        if name == 'request.json':
            path = root / name
        else:
            run_id = state.get('run_id', '')
            if not re.fullmatch(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{6}', run_id):
                raise HTTPException(404, 'Run evidence not available')
            path = root / 'evidence' / 'flights' / run_id / name
        if not path.is_file():
            raise HTTPException(404, 'Evidence file not available')
        return FileResponse(path, filename=name)
