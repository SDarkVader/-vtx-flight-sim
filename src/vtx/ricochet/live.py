"""Live server adapter for RicochetCraft & RicochetLakeWorld.

Keeps Ricochet-specific schemas, telemetry, water environment controls, and run
export helpers cleanly decoupled from `src/vtx/live_server.py`.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Literal

import mujoco as mj
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.spatial.transform import Rotation

from vtx.ricochet.mass_register import DEFAULT_REGISTER_VERSION, PropulsionInstallation
from vtx.ricochet.plant import RICOCHET_SURFACE_LIMITS, RicochetCraft
from vtx.water.datum import WaterEnvironmentConfig
from vtx.water.lake_world import RicochetLakeWorld

RICOCHET_VARIANTS = ('ricochet-rc01-f03', 'ricochet-concept-a', 'ricochet-rc01-dev')

_RICOCHET_META_KEYS = frozenset({
    'schema', 'schema_id', 'authority', 'expected_run_id', 'observation_id',
    'pilot_id', 'pilot_epoch', 'pilot_run_id', 'reason',
    'text', 'command_text', 'intent', 'cmd', 'command', 'surfaces',
})

_CHANNEL_ALIAS_GROUPS: dict[str, tuple[str, ...]] = {
    'throttle': ('throttle', 'power', 'thrust', 'thrust_cmd', 'engine', 'rpm_frac', 'throttle_pct'),
    'differential_thrust': ('differential_thrust', 'diff_thrust', 'differential', 'yaw_thrust', 'split_thrust', 'asymmetric_thrust'),
    'rudder_deg': ('rudder_deg', 'rudder', 'helm_deg', 'helm', 'yaw_deg', 'yaw', 'rudder_rad', 'rudder_norm', 'rudder_frac'),
    'elevator_deg': ('elevator_deg', 'elevator', 'elevators', 'pitch_deg', 'pitch', 'stabilator', 'stab', 'elevator_rad', 'elevator_norm'),
    'aileron_deg': ('aileron_deg', 'aileron', 'ailerons', 'roll_deg', 'roll', 'bank_deg', 'bank', 'aileron_rad', 'aileron_norm'),
    'reverse_bucket': ('reverse_bucket', 'reverser', 'reverse', 'bucket', 'buckets', 'reverse_thrust', 'reverse_deg', 'reverser_deg', 'reverse_pct'),
    'ski_incidence_deg': ('ski_incidence_deg', 'ski_incidence', 'ski_collective', 'ski_pitch', 'ski_aoa', 'skis_deg', 'collective'),
    'ski_differential_deg': ('ski_differential_deg', 'ski_differential', 'ski_diff', 'ski_roll', 'ski_bank'),
    'aft_ski_incidence_deg': ('aft_ski_incidence_deg', 'aft_ski', 'stern_ski', 'aft_ski_deg', 'stern_ski_deg'),
    'ecu_assist': ('ecu_assist', 'ecu', 'trim_ecu'),
}

_EXTENDED_CHANNEL_LIMITS: dict[str, dict[str, float]] = {
    'ski_incidence_deg': {'min': -6.0, 'max': 12.0},
    'ski_differential_deg': {'min': -4.0, 'max': 4.0},
    'aft_ski_incidence_deg': {'min': -8.0, 'max': 10.0},
    'ecu_assist': {'min': 0.0, 'max': 1.0},
}

_ALIAS_TO_CHANNEL: dict[str, tuple[str, str]] = {
    alias: (chan, alias)
    for chan, aliases in _CHANNEL_ALIAS_GROUPS.items()
    for alias in aliases
}

_MAGNITUDE_WORDS: dict[str, float] = {
    'full': 1.0, 'max': 1.0, 'hard': 1.0, 'all': 1.0, 'deploy': 1.0, 'open': 1.0, 'engage': 1.0, 'engaged': 1.0, 'on': 1.0, 'reverse': 1.0,
    'three-quarter': 0.75, 'three quarter': 0.75, '3/4': 0.75, 'cruise': 0.75, 'high': 0.85,
    'half': 0.5, 'medium': 0.5, 'mid': 0.5, 'moderate': 0.5, '1/2': 0.5,
    'quarter': 0.25, 'gentle': 0.25, 'slight': 0.25, 'light': 0.25, 'touch': 0.2, 'slow': 0.25, 'low': 0.25, '1/4': 0.25,
    'idle': 0.08,
    'zero': 0.0, 'stop': 0.0, 'off': 0.0, 'cut': 0.0, 'stow': 0.0, 'stowed': 0.0, 'retract': 0.0, 'retracted': 0.0,
    'closed': 0.0, 'neutral': 0.0, 'center': 0.0, 'centered': 0.0, 'level': 0.0, 'straight': 0.0, 'ahead': 0.0, 'forward': 0.0,
}

_SIGNED_DIR_WORDS: dict[str, dict[str, float]] = {
    'rudder_deg': {'port': +1.0, 'left': +1.0, 'starboard': -1.0, 'stbd': -1.0, 'right': -1.0},
    'elevator_deg': {'up': +1.0, 'nose up': +1.0, 'pitch up': +1.0, 'pull': +1.0, 'climb': +1.0, 'down': -1.0, 'nose down': -1.0, 'pitch down': -1.0, 'push': -1.0, 'dive': -1.0},
    'aileron_deg': {'right': +1.0, 'starboard': +1.0, 'stbd': +1.0, 'bank right': +1.0, 'roll right': +1.0, 'left': -1.0, 'port': -1.0, 'bank left': -1.0, 'roll left': -1.0},
    'differential_thrust': {'port': +1.0, 'left': +1.0, 'yaw left': +1.0, 'starboard': -1.0, 'stbd': -1.0, 'right': -1.0, 'yaw right': -1.0},
    'ski_incidence_deg': {'up': +1.0, 'ski up': +1.0, 'skis up': +1.0, 'nose up': +1.0, 'pitch up': +1.0, 'raise': +1.0, 'positive': +1.0, 'down': -1.0, 'ski down': -1.0, 'skis down': -1.0, 'nose down': -1.0, 'pitch down': -1.0, 'lower': -1.0, 'negative': -1.0},
    'ski_differential_deg': {'right': +1.0, 'starboard': +1.0, 'stbd': +1.0, 'bank right': +1.0, 'roll right': +1.0, 'ski bank right': +1.0, 'port up': +1.0, 'left': -1.0, 'port': -1.0, 'bank left': -1.0, 'roll left': -1.0, 'ski bank left': -1.0, 'stbd up': -1.0},
    'aft_ski_incidence_deg': {'up': +1.0, 'aft ski up': +1.0, 'stern ski up': +1.0, 'raise': +1.0, 'positive': +1.0, 'down': -1.0, 'aft ski down': -1.0, 'stern ski down': -1.0, 'lower': -1.0, 'negative': -1.0},
}


def is_ricochet_variant(variant: str | None) -> bool:
    return bool(variant and variant in RICOCHET_VARIANTS)


def hull_variant_for_airframe(airframe_variant: str | None) -> str:
    if airframe_variant == 'ricochet-concept-a':
        return 'concept_a'
    return 'f03'


def _resolve_scalar_command(
    channel: str,
    raw_val: Any,
    source_key: str,
    notes: list[str],
) -> float:
    """Resolve numeric, unit-tagged, percentage, sequence, or qualitative pilot values into mechanical bounds."""
    lim = RICOCHET_SURFACE_LIMITS.get(channel) or _EXTENDED_CHANNEL_LIMITS[channel]
    lo, hi = float(lim['min']), float(lim['max'])
    abs_max = max(abs(lo), abs(hi))

    if isinstance(raw_val, bool):
        val = 1.0 if raw_val else 0.0
    elif isinstance(raw_val, (list, tuple)):
        if len(raw_val) == 2 and channel == 'aileron_deg':
            # Allow (port_deg, stbd_deg) pair -> effective roll deflection 0.5 * (stbd - port)
            val = 0.5 * (float(raw_val[1]) - float(raw_val[0]))
        elif len(raw_val) > 0:
            val = float(raw_val[0])
        else:
            raise ValueError(f'Empty sequence for {channel}')
    elif isinstance(raw_val, (int, float)):
        val = float(raw_val)
        if not math.isfinite(val):
            raise ValueError(f'Non-finite value for {channel}')
        if source_key.endswith('_rad'):
            val = math.degrees(val)
            notes.append(f'{source_key}->deg')
        elif source_key.endswith(('_norm', '_frac')):
            val = val * abs_max
            notes.append(f'{source_key}->deg')
        elif source_key.endswith('_pct') or (channel in ('throttle', 'reverse_bucket', 'ecu_assist') and val > 1.0 and val <= 100.0 and source_key != 'reverse_deg'):
            # Interpret values in (1, 100] on fractional channels? Wait: only if _pct or string '%' unless ambiguous!
            # For safety on raw > 1 without %, clamp and note below unless source_key implies deg/pct:
            if source_key.endswith('_pct'):
                val = val * 0.01 * hi
                notes.append(f'{source_key}->frac')
        if channel == 'reverse_bucket' and source_key in ('reverse_deg', 'reverser_deg'):
            val = val / 85.0
            notes.append(f'{source_key}->frac')
    elif isinstance(raw_val, str):
        s = raw_val.strip().lower()
        if not s:
            raise ValueError(f'Empty command string for {channel}')
        num_match = re.search(r'[-+]?\d+(?:\.\d+)?', s)
        dir_map = _SIGNED_DIR_WORDS.get(channel, {})
        dir_sign = None
        for phrase in sorted(dir_map, key=len, reverse=True):
            if re.search(rf'\b{re.escape(phrase)}\b', s):
                dir_sign = dir_map[phrase]
                break

        if num_match:
            num = float(num_match.group(0))
            if '%' in s:
                span = (hi if (dir_sign or 1.0) > 0 else abs(lo)) if dir_sign is not None else (abs_max if channel not in ('reverse_bucket', 'throttle', 'ecu_assist') else 1.0)
                val = (num * 0.01) * span
                if dir_sign is not None and num >= 0:
                    val = dir_sign * abs(val)
            elif 'rad' in s:
                val = math.degrees(num)
                if dir_sign is not None and num >= 0 and lo < 0:
                    val = dir_sign * abs(val)
            else:
                if channel == 'reverse_bucket' and ('deg' in s or source_key in ('reverse_deg', 'reverser_deg')):
                    val = num / 85.0
                elif dir_sign is not None and num >= 0 and lo < 0:
                    val = dir_sign * abs(num)
                else:
                    val = num
        else:
            mag = None
            for word in sorted(_MAGNITUDE_WORDS, key=len, reverse=True):
                if re.search(rf'\b{re.escape(word)}\b', s):
                    mag = _MAGNITUDE_WORDS[word]
                    break
            if channel in ('throttle', 'reverse_bucket', 'ecu_assist'):
                if mag is None:
                    raise ValueError(f'Unrecognized qualitative {channel} command: {raw_val!r}')
                val = mag
            else:
                if dir_sign is not None:
                    frac = 0.5 if mag is None else mag
                    span = hi if dir_sign > 0 else abs(lo)
                    val = dir_sign * frac * span
                elif mag is not None and mag == 0.0:
                    val = 0.0
                elif mag is not None and channel == 'differential_thrust':
                    val = mag
                else:
                    raise ValueError(f'Ambiguous signed {channel} command without direction: {raw_val!r}')
        notes.append(f'{source_key}:{raw_val!r}->{round(val, 3)}')
    else:
        raise ValueError(f'Unsupported command value type for {channel}: {type(raw_val).__name__}')

    clamped = float(np.clip(val, lo, hi))
    if abs(clamped - val) > 1e-6:
        notes.append(f'{channel} clamped {round(val, 3)}->{round(clamped, 3)}')
    return clamped


def _parse_text_command_clauses(text: str, notes: list[str]) -> dict[str, float]:
    """Parse free-form pilot command clauses like 'half throttle, hard port rudder, stow reverser'."""
    out: dict[str, float] = {}
    clauses = [c.strip() for c in re.split(r'[,;\n]+|\band\b', text, flags=re.IGNORECASE) if c.strip()]
    for clause in clauses:
        low = clause.lower()
        # Handle ski, ECU, and reverse bucket synonyms cleanly before rudder/elevator keyword search
        matched_chan: str | None = None
        if any(k in low for k in ('aft ski', 'aft_ski', 'stern ski', 'stern_ski')):
            matched_chan = 'aft_ski_incidence_deg'
        elif any(k in low for k in ('ski diff', 'ski_diff', 'ski bank', 'ski roll', 'ski differential', 'differential ski')):
            matched_chan = 'ski_differential_deg'
        elif any(k in low for k in ('ski', 'skis', 'collective', 'foil incidence')):
            matched_chan = 'ski_incidence_deg'
        elif any(k in low for k in ('ecu', 'trim assist', 'trim_ecu')):
            matched_chan = 'ecu_assist'
        elif any(k in low for k in ('reverser', 'reverse bucket', 'reverse thrust', 'bucket', 'stow', 'deploy')):
            matched_chan = 'reverse_bucket'
        elif any(k in low for k in ('diff', 'asymmetric', 'split thrust')):
            matched_chan = 'differential_thrust'
        elif any(k in low for k in ('rudder', 'helm', 'yaw')):
            matched_chan = 'rudder_deg'
        elif any(k in low for k in ('elevator', 'pitch', 'nose ', 'stabilator', 'stab')):
            matched_chan = 'elevator_deg'
        elif any(k in low for k in ('aileron', 'roll', 'bank')):
            matched_chan = 'aileron_deg'
        elif any(k in low for k in ('throttle', 'power', 'thrust', 'engine', 'idle', 'ahead')):
            matched_chan = 'throttle'
        elif any(k in low for k in ('port', 'starboard', 'stbd')):
            matched_chan = 'rudder_deg'
        if matched_chan is not None:
            out[matched_chan] = _resolve_scalar_command(matched_chan, clause, f'text({matched_chan})', notes)
    return out


def normalize_ricochet_action(body: dict[str, Any]) -> dict[str, Any]:
    """Resolve partial, aliased, unit-tagged, qualitative, and out-of-range Ricochet pilot commands."""
    if not isinstance(body, dict):
        return body
    raw = dict(body)
    notes: list[str] = []
    # Allow nested cmd/command/surfaces envelope gracefully
    for nest_key in ('cmd', 'command', 'surfaces'):
        nested = raw.pop(nest_key, None)
        if isinstance(nested, dict):
            for nk, nv in nested.items():
                raw.setdefault(nk, nv)

    normalized: dict[str, Any] = {}
    # Copy known metadata fields cleanly
    for mk in ('schema', 'schema_id', 'authority', 'expected_run_id', 'observation_id', 'pilot_id', 'pilot_epoch', 'pilot_run_id', 'reason'):
        if mk in raw and raw[mk] is not None:
            normalized[mk] = raw[mk]
    normalized.setdefault('schema', 'ricochet-1')

    # Parse optional free-form text intent first so explicit structured keys override if both supplied
    for tk in ('text', 'command_text', 'intent'):
        tval = raw.pop(tk, None)
        if isinstance(tval, str) and tval.strip():
            parsed_clauses = _parse_text_command_clauses(tval, notes)
            for ck, cv in parsed_clauses.items():
                normalized[ck] = cv

    # Resolve structured channels & aliases
    for key, val in raw.items():
        if key in _RICOCHET_META_KEYS:
            continue
        if key in _ALIAS_TO_CHANNEL:
            canon_chan, src_key = _ALIAS_TO_CHANNEL[key]
            if val is not None:
                normalized[canon_chan] = _resolve_scalar_command(canon_chan, val, src_key, notes)
        else:
            # Leave unknown keys intact so strict Pydantic extra='forbid' still catches accidental garbage
            normalized[key] = val

    if notes:
        base_reason = str(normalized.get('reason') or 'ricochet operator command').strip()
        suffix = f" [resolved: {'; '.join(notes[:4])}]"
        normalized['reason'] = (base_reason + suffix)[:256]
    return normalized


class RicochetAction(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, populate_by_name=True)

    schema_id: Literal['ricochet-1'] = Field(default='ricochet-1', alias='schema')
    authority: Literal['colin', 'manual'] = 'manual'
    expected_run_id: str | None = None
    observation_id: int | None = None
    pilot_id: str | None = None
    pilot_epoch: int | None = None
    pilot_run_id: str | None = None
    reason: str = Field(default='ricochet operator command', max_length=256)
    throttle: float | None = Field(default=None, ge=0.0, le=1.0)
    differential_thrust: float | None = Field(default=None, ge=-1.0, le=1.0)
    rudder_deg: float | None = Field(default=None, ge=-30.0, le=30.0)
    elevator_deg: float | None = Field(default=None, ge=-20.0, le=20.0)
    aileron_deg: float | None = Field(default=None, ge=-25.0, le=25.0)
    reverse_bucket: float | None = Field(default=None, ge=0.0, le=1.0)
    ski_incidence_deg: float | None = Field(default=None, ge=-6.0, le=12.0)
    ski_differential_deg: float | None = Field(default=None, ge=-4.0, le=4.0)
    aft_ski_incidence_deg: float | None = Field(default=None, ge=-8.0, le=10.0)
    ecu_assist: float | None = Field(default=None, ge=0.0, le=1.0)


def default_interactive_water_config() -> WaterEnvironmentConfig:
    """Realistic open-lake sea state enabled by default on live UI switches to Ricochet Lake."""
    return WaterEnvironmentConfig(
        wave_mode='irregular',
        wave_height_m=0.35,
        wave_period_s=3.8,
        wave_direction_deg=205.0,
        wind_speed_mps=4.5,
        wind_direction_deg=210.0,
        current_speed_mps=0.35,
        wake_enabled=True,
        whirlpools_enabled=True,
    )


def make_aircraft(
    world: Any,
    airframe_variant: str = 'ricochet-rc01-f03',
    water_config: WaterEnvironmentConfig | None = None,
    load_case: str | None = 'LC-01',
    wind_world_mps: list[float] | tuple[float, float, float] | None = None,
    register_version: str = DEFAULT_REGISTER_VERSION,
    fuel_state: str | None = None,
    fuel_mass_kg: float | None = None,
    propulsion_installation: PropulsionInstallation | None = None,
    propulsion_off: bool | None = None,
    profile: str | None = None,
) -> RicochetCraft:
    if not isinstance(world, RicochetLakeWorld):
        raise ValueError('Ricochet craft requires the ricochet_lake environment')
    cfg = water_config or WaterEnvironmentConfig()
    if wind_world_mps is not None and any(abs(float(x)) > 1e-6 for x in wind_world_mps):
        wx, wy = float(wind_world_mps[0]), float(wind_world_mps[1])
        spd = math.hypot(wx, wy)
        deg = math.degrees(math.atan2(wy, wx)) % 360.0
        cfg = WaterEnvironmentConfig(**{**cfg.to_dict(), 'wind_speed_mps': spd, 'wind_direction_deg': deg})
    craft = RicochetCraft(
        world=world,
        variant=airframe_variant,
        hull_variant=hull_variant_for_airframe(airframe_variant),
        load_case=load_case,
        water_config=cfg,
        register_version=register_version,
        fuel_state=fuel_state,
        fuel_mass_kg=fuel_mass_kg,
        propulsion_installation=propulsion_installation,
        propulsion_off=propulsion_off,
        profile=profile,
    )
    return craft


def sensor_observation(lab: Any) -> dict[str, Any]:
    """Pilot-visible cockpit & surface telemetry only (no truth internal forces, inertia, or contact manifolds)."""
    p: RicochetCraft = lab.aircraft
    d = p.data
    m = p.model
    bid = p.bids['airframe']
    q = d.xquat[bid]
    euler = Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_euler('xyz', degrees=True)
    vel = np.zeros(6, dtype=np.float64)
    mj.mj_objectVelocity(m, d, mj.mjtObj.mjOBJ_BODY, bid, vel, 0)
    rot = d.xmat[bid].reshape(3, 3)
    vel_body = rot.T @ vel[3:]
    pos = d.xpos[bid]
    clearance = p.ground_clearance()
    noise = lab.sensor_rng.normal

    hydro = p.last_hydro.to_telemetry_dict() if p.last_hydro else {}
    mp = p.mass_properties()
    whirl = dict(getattr(p, '_last_whirlpool_hazard', {}) or {})
    wake = p.water_field.get_wake_state()
    ctrl_surf = p.control_surface_telemetry()
    water_cfg = p.water_config.to_dict()

    lamps = []
    if p.crashed:
        lamps.append('IMPACT')
    if clearance is not None and clearance < 0.2:
        lamps.append('SHALLOW_KEEL_CLEARANCE')
    if whirl.get('in_core'):
        lamps.append('WHIRLPOOL_CAPTURE')
    elif whirl.get('in_influence'):
        lamps.append('WHIRLPOOL_SHEAR')
    if not mp.get('waterproof', True):
        lamps.append('HULL_UNSEALED')
    if float(mp.get('flood_water_kg', 0.0)) > 5.0:
        lamps.append('FLOODING')
    if float(mp.get('reserve_buoyancy_kg', 1.0)) <= 0.0:
        lamps.append('SINKS')
    if float(p.fuel[0]) <= 1e-4:
        lamps.append('FUEL_EXHAUSTED')
    if 'SERVO_SATURATED' in p.flags:
        lamps.append('SERVO_SATURATED')
    if getattr(p, 'capsized', False) or 'CAPSIZED' in p.flags:
        lamps.append('CAPSIZED')

    rud_fb = float(ctrl_surf['rudder']['achieved_deg'])
    elev_fb = float(ctrl_surf['elevator']['achieved_deg'])
    ail_p_fb = float(ctrl_surf['aileron']['port_achieved_deg'])
    ail_s_fb = float(ctrl_surf['aileron']['stbd_achieved_deg'])
    rev_p_fb = float(ctrl_surf['reverse_bucket']['port_achieved_deg'])
    rev_s_fb = float(ctrl_surf['reverse_bucket']['stbd_achieved_deg'])
    rev_frac = float(ctrl_surf['reverse_bucket']['achieved_frac'])

    draft_m = float(hydro.get('draft_m', 0.0))
    freeboard_m = float(hydro.get('freeboard_min_m', 0.0))
    water_depth_m = float(hydro.get('mean_water_depth_m', 0.0))

    obs = dict(
        observation_id=lab.obs_id,
        t_s=round(float(d.time), 3),
        wall_utc=datetime.now(timezone.utc).isoformat(),
        action_schema='ricochet-1',
        command_mode='hold_until_changed',
        frame_labels=dict(
            attitude='roll right-down +, pitch nose-up +, yaw nose-left + (ENU heading)',
            differential_thrust='fraction in [-1, +1]; + stbd > port (port / nose-left yaw), - port > stbd (starboard / nose-right yaw)',
            rudder='deg in [-30, +30]; + port / nose-left yaw, - starboard / nose-right yaw',
            elevator='deg in [-20, +20]; + TE up / nose-up pitch, - TE down / nose-down pitch',
            aileron='deg in [-25, +25]; + right roll (stbd TE up, port TE down), - left roll',
            reverse_bucket='fraction in [0, 1] (0..85 deg deflector across ducted fan exit)',
        ),
        gnss_xy_m=np.round(pos[:2] + noise(0, 0.015, 2), 2).tolist(),
        baro_m=round(float(pos[2] + noise(0, 0.01)), 3),
        radar_clearance_m=round(float(clearance + noise(0, 0.005)), 3) if clearance is not None else None,
        water_clearance_m=round(water_depth_m - draft_m, 3),
        water_depth_m=round(water_depth_m, 3),
        draft_m=round(draft_m, 3),
        freeboard_m=round(freeboard_m, 3),
        attitude_xyz_deg=np.round(euler + noise(0, 0.008, 3), 3).tolist(),
        heading_deg=round(float(euler[2] % 360.0), 2),
        gyro_world_deg_s=np.round(np.degrees(vel[:3]) + noise(0, 0.008, 3), 3).tolist(),
        gnss_velocity_mps=np.round(vel[3:] + noise(0, 0.005, 3), 3).tolist(),
        body_velocity_mps=np.round(vel_body, 3).tolist(),
        airspeed_m_s=round(float(np.linalg.norm(vel[3:] - p.wind)), 2),
        fan_rpm=[round(float(r['rpm']), 1) for r in p.rotors],
        spool_fraction=[round(float(r['spool_fraction']), 3) for r in p.rotors],
        shaft_torque_nm=[round(float(r['torque_nm']), 1) for r in p.rotors],
        engine_shaft_kw=round(float(p.power['engine_w']) / 1000.0, 2),
        servo_power_kw=round(float(p.power.get('servo_w', 0.0)) / 1000.0, 3),
        fuel_kg=np.round(p.fuel, 4).tolist(),
        energy_remaining_kwh=round(float(p.energy.get('remaining_kwh', 0.0)), 4),
        rudder_feedback_deg=round(rud_fb + float(noise(0, 0.02)), 2),
        elevator_feedback_deg=round(elev_fb + float(noise(0, 0.02)), 2),
        aileron_feedback_deg=[round(ail_p_fb, 2), round(ail_s_fb, 2)],
        reverse_bucket_feedback_deg=[round(rev_p_fb, 2), round(rev_s_fb, 2)],
        reverse_bucket_fraction=round(rev_frac, 3),
        control_surfaces=ctrl_surf,
        surface_limits=p.surface_limits,
        command=dict(p.command),
        command_help=(
            'Partial updates supported under hold_until_changed; numeric, unit-tagged '
            '(deg/rad/%), qualitative phrases (e.g. "hard port", "nose up", "deploy"), '
            'and natural-language "text" clauses are resolved and clamped to surface_limits.'
        ),
        waterproof=bool(mp.get('waterproof', True)),
        flood_water_kg=round(float(mp.get('flood_water_kg', 0.0)), 1),
        reserve_buoyancy_kg=round(float(mp.get('reserve_buoyancy_kg', 0.0)), 1),
        load_case=mp.get('load_case', p.mass_register.load_case),
        register_version=mp.get('register_version', p.mass_register.register_version),
        fuel_state=mp.get('fuel_state', p.mass_register.fuel_state),
        fuel_mass_kg=round(float(mp.get('fuel_mass_kg', p.mass_register.fuel_mass_kg)), 4),
        propulsion_installation=mp.get('propulsion_installation', p.mass_register.propulsion_installation),
        propulsion_off=bool(mp.get('propulsion_off', p.mass_register.propulsion_off)),
        wave_height_m=round(float(water_cfg.get('wave_height_m', 0.0)), 3),
        wave_period_s=round(float(water_cfg.get('wave_period_s', 0.0)), 2),
        wave_direction_deg=round(float(water_cfg.get('wave_direction_deg', 0.0)), 1),
        current_speed_mps=round(float(water_cfg.get('current_speed_mps', 0.0)), 2),
        wind_world_mps=[round(float(x), 2) for x in p.wind],
        whirlpool_hazard=whirl,
        vessel_wake=wake,
        water_config=water_cfg,
        warning_lamps=lamps,
        configuration=dict(
            airframe_revision=p.provenance['revision'],
            airframe_variant=p.variant,
            hull_variant=p.hull_bundle.variant_id,
            hull_geometry_sha256=p.provenance['hull_geometry_sha256'],
            solver_version=p.provenance['solver_version'],
            register_version=mp.get('register_version', p.mass_register.register_version),
            load_case=mp.get('load_case', p.mass_register.load_case),
            fuel_state=mp.get('fuel_state', p.mass_register.fuel_state),
            fuel_mass_kg=round(float(mp.get('fuel_mass_kg', p.mass_register.fuel_mass_kg)), 4),
            propulsion_installation=mp.get('propulsion_installation', p.mass_register.propulsion_installation),
            propulsion_off=bool(mp.get('propulsion_off', p.mass_register.propulsion_off)),
        ),
        scheduler_backlog_s=round(lab.clock_lag_s, 3),
        mission=lab.mission,
        authority=lab.authority,
        active=lab.active,
        paused=lab.paused,
        time_scale=lab.time_scale,
        sensor_status='Ricochet LAKE MuJoCo 400 Hz + HybridWaterField pilot avionics (full ROM + hold_until_changed)',
    )
    if getattr(p, 'profile_id', None) is not None:
        obs['profile_id'] = p.profile_id
        obs['model_revision'] = getattr(p, 'model_revision', p.profile_id)
        obs['model_name'] = getattr(p, 'model_name', p.profile_id)
        obs['capsized'] = bool(getattr(p, 'capsized', False))
        if 'skis' in ctrl_surf:
            obs['ski_feedback_deg'] = [
                round(float(ctrl_surf['skis']['port_achieved_deg']), 2),
                round(float(ctrl_surf['skis']['stbd_achieved_deg']), 2),
            ]
        if 'aft_ski' in ctrl_surf:
            obs['aft_ski_feedback_deg'] = round(float(ctrl_surf['aft_ski']['achieved_deg']), 2)
        if 'ecu' in ctrl_surf:
            obs['ecu_status'] = dict(ctrl_surf['ecu'])
        if getattr(p, 'last_ski_telemetry', None):
            obs['ski_telemetry'] = dict(p.last_ski_telemetry)
    return obs


def integrate(lab: Any) -> None:
    p: RicochetCraft = lab.aircraft
    while lab.next_pending_action < len(lab.action_log):
        row = lab.action_log[lab.next_pending_action]
        if row.get('cancelled'):
            lab.next_pending_action += 1
            continue
        if p.data.time < row['apply_t_s']:
            break
        lab.next_pending_action += 1
        if row['issued']['authority'] != lab.authority:
            row['cancelled'] = True
            lab.log('control_cancelled', dict(sequence=row['sequence'], reason='Control authority changed before application'))
            continue
        cmd = {k: row['issued'][k] for k in p.command if k in row['issued'] and row['issued'][k] is not None}
        p.set_command(cmd)
        row['applied'] = True
        lab.log('control_applied', dict(sequence=row['sequence'], requested=cmd, applied_sim_t_s=float(p.data.time)))
    p.step()
    if p.data.time - lab.last_audit_t >= 0.05:
        lab.last_audit_t = float(p.data.time)
        lab.log('physics_audit', p.physical_snapshot())
        lab.sensor_observation()
        lab.checkpoint()


def water_frame(world: Any, aircraft: Any | None = None) -> dict[str, Any] | None:
    """Basin + craft-centered high-resolution water elevation/velocity grid from HybridWaterField."""
    if not isinstance(world, RicochetLakeWorld):
        return None
    wf = getattr(aircraft, 'water_field', None)
    if wf is None:
        return None
    t_s = float(aircraft.data.time) if aircraft is not None else 0.0
    g = wf.elevation_grid(nx=41, ny=25, t=t_s)

    # Craft-centered 65x65 (2.0 m resolution, 128x128 m) solver patch snapped to 2.0 m world grid
    bid_af = getattr(aircraft, 'bids', {}).get('airframe') if aircraft is not None else None
    if aircraft is not None and bid_af is not None:
        vx, vy = float(aircraft.data.xpos[bid_af, 0]), float(aircraft.data.xpos[bid_af, 1])
    else:
        dep = getattr(world, 'default_departure', (0.0, 0.0))
        vx, vy = float(dep[0]), float(dep[1])
    patch_half = 64.0
    cx = round(vx / 2.0) * 2.0
    cy = round(vy / 2.0) * 2.0
    px0, px1 = cx - patch_half, cx + patch_half
    py0, py1 = cy - patch_half, cy + patch_half
    pnx = pny = 65
    pxs = np.linspace(px0, px1, pnx, dtype=np.float64)
    pys = np.linspace(py0, py1, pny, dtype=np.float64)
    pxg, pyg = np.meshgrid(pxs, pys)
    psamp = wf.evaluate(pxg, pyg, t=t_s)
    local_patch = {
        'nx': pnx,
        'ny': pny,
        'x_min_m': float(px0),
        'x_max_m': float(px1),
        'y_min_m': float(py0),
        'y_max_m': float(py1),
        'elevation_m': np.round(psamp.eta, 3).tolist(),
        'depth_m': np.round(psamp.depth, 3).tolist(),
        'u_mps': np.round(psamp.velocity[..., 0], 3).tolist(),
        'v_mps': np.round(psamp.velocity[..., 1], 3).tolist(),
    }

    return {
        'nx': int(g['nx']),
        'ny': int(g['ny']),
        'x_min_m': float(-g['half_x']),
        'x_max_m': float(g['half_x']),
        'y_min_m': float(-g['half_y']),
        'y_max_m': float(g['half_y']),
        'water_level_m': float(g['water_level_m']),
        't_s': round(t_s, 4),
        'elevation_m': g['eta'],
        'local_patch': local_patch,
        'vessel_wake': wf.get_wake_state(),
        'whirlpools': list(getattr(world, 'whirlpools', [])),
        'water_config': wf.config.to_dict(),
        'conservation': wf.shallow.conservation_metrics(),
    }


def export_run_bundle(lab: Any) -> dict[str, Any]:
    p = lab.aircraft
    if not getattr(p, 'is_ricochet', False):
        raise ValueError('Water test export is only available when RicochetCraft is loaded')
    return {
        'run_id': lab.run_id,
        'active': lab.active,
        'paused': lab.paused,
        'time_scale': lab.time_scale,
        'exported_utc': datetime.now(timezone.utc).isoformat(),
        'environment': {
            'key': getattr(lab.world, 'environment_key', 'ricochet_lake'),
            'id': lab.world.id,
            'version': lab.world.version,
        },
        'water_config': p.water_config.to_dict(),
        'random_seed': p.water_config.wave_seed,
        'geometry_hash': p.provenance['hull_geometry_sha256'],
        'solver_version': p.provenance['solver_version'],
        'provenance': p.provenance,
        'mass_properties': p.mass_properties(),
        'water_conservation': p.water_field.shallow.conservation_metrics(),
        'telemetry': p.physical_snapshot(),
        'recent_decisions': [{k: v for k, v in a.items() if k != 'observation'} for a in lab.action_log[-32:]],
    }
