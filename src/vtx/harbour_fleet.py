"""Native, versioned Airport marine fleet. Legacy flight plants are untouched.

All boats collide in one MuJoCo scene. Original PR57 per-vessel models remain
force adapters: the upstream hydro assembly assumes every model body belongs
to one vessel. Only the shared scene advances rigid-body time. One polygon-
masked water field advances once and retains a wake for each identified boat.
"""

from __future__ import annotations
from copy import deepcopy
from dataclasses import fields
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import xml.etree.ElementTree as ET
import numpy as np
import mujoco as mj

DT = 0.01
HYDRO_STRIDE = 5
CADENCE = dict(
    rigid_hz=100,
    rigid_dt_s=DT,
    hydro_hz=20,
    hydro_stride_steps=HYDRO_STRIDE,
    hydro_force_reconstruction="causal-linear-midpoint-ab2-v1",
    swe_hz=10,
    swe_interval_s=0.1,
)
SCHEMA = "vtx-airport-harbour-fleet-v2"
ROOT = Path(__file__).resolve().parents[2]


def _pack(value):
    if isinstance(value, np.ndarray):
        return {"array": value.tolist()}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, tuple):
        return {"tuple": [_pack(v) for v in value]}
    if isinstance(value, list):
        return [_pack(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _pack(v) for k, v in value.items()}
    return value


def _unpack(value):
    if isinstance(value, dict):
        if set(value) == {"array"}:
            return np.asarray(value["array"], dtype=float)
        if set(value) == {"tuple"}:
            return tuple(_unpack(v) for v in value["tuple"])
        return {k: _unpack(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unpack(v) for v in value]
    return value


def dependency_fingerprint():
    source = Path(__file__).parent
    paths = [Path(__file__), source / "harbour_water.py"]
    paths += list((source / "ricochet").glob("*.py")) + list(
        (source / "water").glob("*.py")
    )
    paths += [
        ROOT / "experiments/ricochet/rc01_f03/model/RC01_F03_cad_stations.npz",
        ROOT / "public/assets/ricochet-concept-a.glb",
    ]
    digest = hashlib.sha256()
    for path in sorted(paths):
        name = path.relative_to(ROOT).as_posix().encode()
        raw = path.read_bytes()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


class _WaterReference:
    """An explicit fleet-internal reference; original single-craft saves unchanged."""

    def __init__(self, water):
        self.water = water

    def __getattr__(self, name):
        return getattr(self.water, name)

    def checkpoint_state(self):
        return {"shared_harbour_water": True}

    def restore_state(self, state):
        if state != {"shared_harbour_water": True}:
            raise ValueError("Invalid shared-water reference")


class HarbourFleet:
    def __init__(self, world, *, vessels=None, water_config=None):
        from .harbour_water import HarbourWorld, HarbourWater
        from .ricochet.plant import RicochetCraft
        from .water.datum import WaterEnvironmentConfig

        self._lock = threading.RLock()
        self.world = HarbourWorld(world)
        self.world_sha256 = self.world.fingerprint
        self.dependencies_sha256 = dependency_fingerprint()
        self.berths = {
            b["id"]: deepcopy(b) for b in self.world.harbour["docks"]["berths"]
        }
        if len(self.berths) != len(self.world.harbour["docks"]["berths"]):
            raise ValueError("Duplicate berth identity")
        if vessels is None:
            vessels = [
                dict(
                    id="ricochet-airport",
                    name="Ricochet · Airport Landing",
                    variant="ricochet-concept-a",
                    berth_id="airport-landing-ricochet",
                ),
                dict(
                    id="ricochet-marina",
                    name="Ricochet · Lantern Marina",
                    variant="ricochet-concept-a",
                    berth_id="lantern-marina-ricochet",
                ),
            ]
        self.definitions = deepcopy(vessels)
        if any(
            set(v) != set(("id", "name", "variant", "berth_id"))
            or not isinstance(v.get("name"), str)
            or not 1 <= len(v["name"]) <= 100
            for v in vessels
        ):
            raise ValueError("Invalid vessel definition")
        ids = [v.get("id") for v in vessels]
        if (
            not 1 <= len(vessels) <= 4
            or len(set(ids)) != len(ids)
            or any(
                not isinstance(i, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", i)
                for i in ids
            )
        ):
            raise ValueError("Fleet requires one to four uniquely identified vessels")
        self.selectedId = ids[0]
        self.occupancy = {}
        self.moorings = {}
        self.events = []
        self.crafts = {}
        self.mappings = {}
        self.step_count = 0
        self._interrupted_step = False
        config = water_config or dict(
            water_level_m=self.world.harbour["waterLevelM"],
            wave_mode="still",
            wind_speed_mps=0.0,
            current_speed_mps=0.0,
            wake_enabled=True,
            whirlpools_enabled=False,
        )
        config = (
            WaterEnvironmentConfig.from_dict(config)
            if isinstance(config, dict)
            else config
        )
        self.water = HarbourWater(self.world, config)
        for definition in self.definitions:
            variant = definition.get("variant")
            if variant not in ("ricochet-concept-a", "ricochet-rc01-f03"):
                raise ValueError(
                    "Unknown harbour vessel variant; no substitution allowed"
                )
            berth_id = definition.get("berth_id")
            berth = self.berths.get(berth_id)
            if berth is None or variant not in berth["compatibleProfileIds"]:
                raise ValueError(
                    "Vessel requires a compatible, explicitly identified berth"
                )
            if berth_id in self.occupancy:
                raise ValueError("Two vessels cannot occupy one berth")
            craft = RicochetCraft(
                self.world,
                variant=variant,
                hull_variant="concept_a"
                if variant == "ricochet-concept-a"
                else "f03_baseline",
                water_config=config,
                load_case="LC-01",
                hydro_stride=HYDRO_STRIDE,
            )
            self._retime_adapter(craft)
            craft.water_field = self.water
            x, y = self.world.to_world([berth["x"], berth["y"]])
            craft.spawn(
                x, y, config.water_level_m, yaw_deg=-math.degrees(berth["heading"])
            )
            self.crafts[definition["id"]] = craft
            self.occupancy[berth_id] = definition["id"]
        self._build_shared_scene()
        for definition in self.definitions:
            boat_id = definition["id"]
            p, h, _ = self._pose(boat_id)
            self.moorings[boat_id] = dict(
                berth_id=definition["berth_id"], xy=p[:2].tolist(), heading=h
            )
        self._geometry = {}
        identity = dict(
            cadence=CADENCE,
            water_grid=self.water.grid_identity,
            model_xml_sha256=self.model_xml_sha256,
        )
        self.dynamics_id = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _retime_adapter(craft):
        """Retiming belongs to this fleet, never the original 400Hz plant.

        Compile the fleet's own adapter XML at 100Hz, keeping measured masses,
        inertial frames and exact collision meshes. The original Ricochet
        module/class defaults and standalone checkpoint contract are intact.
        """
        original = craft.model
        root = ET.fromstring(craft.xml)
        root.find("option").set("timestep", str(DT))
        craft.xml = ET.tostring(root, encoding="unicode")
        craft.model = mj.MjModel.from_xml_string(craft.xml)
        craft.data = mj.MjData(craft.model)
        if (craft.model.nbody, craft.model.njnt, craft.model.nu) != (
            original.nbody,
            original.njnt,
            original.nu,
        ):
            raise ValueError("Retimed adapter topology differs")
        craft.model.hfield_data[:] = original.hfield_data
        for key in ("body_mass", "body_inertia", "body_ipos", "body_iquat"):
            getattr(craft.model, key)[:] = getattr(original, key)
        mj.mj_setConst(craft.model, craft.data)
        mj.mj_forward(craft.model, craft.data)
        craft._model_xml_sha256 = hashlib.sha256(craft.xml.encode()).hexdigest()
        craft.DT = DT

    def _build_shared_scene(self):
        craft_list = list(self.crafts.values())
        base = ET.fromstring(craft_list[0].xml)
        vessel_bits = [1 << (i + 1) for i in range(len(craft_list))]
        all_bits = sum(vessel_bits)
        ref = {
            "body",
            "body1",
            "body2",
            "joint",
            "joint1",
            "joint2",
            "site",
            "site1",
            "site2",
            "geom",
            "geom1",
            "geom2",
            "material",
            "mesh",
            "tendon",
            "tendon1",
            "tendon2",
            "target",
            "objname",
            "refname",
        }
        for geom in base.find("worldbody").findall("geom"):
            geom.set("conaffinity", str(all_bits))
        for i, craft in enumerate(craft_list):
            root = base if i == 0 else ET.fromstring(craft.xml)
            prefix = "" if i == 0 else f"fleet{i}_"
            if i:
                names = {n.get("name") for n in root.iter() if n.get("name")}
                for element in root.iter():
                    for key, value in list(element.attrib.items()):
                        if (key == "name" or key in ref) and value in names:
                            element.set(key, prefix + value)
            body = root.find("worldbody").find(f"body[@name='{prefix}airframe']")
            for geom in body.iter("geom"):
                if int(geom.get("contype", "1")) == 2:
                    geom.set("contype", str(vessel_bits[i]))
                    geom.set("conaffinity", str(1 | (all_bits ^ vessel_bits[i])))
            if i:
                for asset in root.find("asset"):
                    if asset.tag != "hfield":
                        base.find("asset").append(deepcopy(asset))
                base.find("worldbody").append(deepcopy(body))
                for tag in ("actuator", "sensor", "equality", "contact", "tendon"):
                    source = root.find(tag)
                    if source is None:
                        continue
                    destination = base.find(tag)
                    if destination is None:
                        destination = ET.SubElement(base, tag)
                    for item in source:
                        destination.append(deepcopy(item))
        for obstacle in self.world.obstacles:
            attrs = (
                dict(type="box", size=" ".join(map(str, obstacle["half"])))
                if obstacle["kind"] == "box"
                else dict(
                    type="cylinder", size=f"{obstacle['half'][0]} {obstacle['half'][2]}"
                )
            )
            ET.SubElement(
                base.find("worldbody"),
                "geom",
                name="airport_" + obstacle["id"],
                pos=" ".join(map(str, obstacle["center"])),
                contype="1",
                conaffinity=str(all_bits),
                **attrs,
            )
        self.xml = ET.tostring(base, encoding="unicode")
        self.model_xml_sha256 = hashlib.sha256(self.xml.encode()).hexdigest()
        self.model = mj.MjModel.from_xml_string(self.xml)
        self.data = mj.MjData(self.model)
        self.model.hfield_data[:] = craft_list[0].model.hfield_data
        for i, (boat_id, craft) in enumerate(self.crafts.items()):
            prefix = "" if i == 0 else f"fleet{i}_"
            joints = []
            for jid in range(craft.model.njnt):
                name = mj.mj_id2name(craft.model, mj.mjtObj.mjOBJ_JOINT, jid)
                shared = mj.mj_name2id(self.model, mj.mjtObj.mjOBJ_JOINT, prefix + name)
                kind = craft.model.jnt_type[jid]
                nq = (
                    7
                    if kind == mj.mjtJoint.mjJNT_FREE
                    else 4
                    if kind == mj.mjtJoint.mjJNT_BALL
                    else 1
                )
                nv = 6 if nq == 7 else 3 if nq == 4 else 1
                oq = int(craft.model.jnt_qposadr[jid])
                sq = int(self.model.jnt_qposadr[shared])
                ov = int(craft.model.jnt_dofadr[jid])
                sv = int(self.model.jnt_dofadr[shared])
                joints.append((oq, sq, nq, ov, sv, nv))
                self.data.qpos[sq : sq + nq] = craft.data.qpos[oq : oq + nq]
                self.data.qvel[sv : sv + nv] = craft.data.qvel[ov : ov + nv]
            bodies = {
                b: mj.mj_name2id(
                    self.model,
                    mj.mjtObj.mjOBJ_BODY,
                    prefix + mj.mj_id2name(craft.model, mj.mjtObj.mjOBJ_BODY, b),
                )
                for b in range(1, craft.model.nbody)
            }
            actuators = {
                a: mj.mj_name2id(
                    self.model,
                    mj.mjtObj.mjOBJ_ACTUATOR,
                    prefix + mj.mj_id2name(craft.model, mj.mjtObj.mjOBJ_ACTUATOR, a),
                )
                for a in range(craft.model.nu)
            }
            self.mappings[boat_id] = dict(
                joints=joints,
                bodies=bodies,
                actuators=actuators,
                bid=bodies[craft.bids["airframe"]],
                gids=[
                    g
                    for g in range(self.model.ngeom)
                    if self.model.geom_bodyid[g] in bodies.values()
                ],
            )
        self._copy_masses()

    def _copy_masses(self):
        state = self._integration_state()
        for boat_id, craft in self.crafts.items():
            for old, new in self.mappings[boat_id]["bodies"].items():
                for key in ("body_mass", "body_inertia", "body_ipos", "body_iquat"):
                    getattr(self.model, key)[new] = getattr(craft.model, key)[old]
        mj.mj_setConst(self.model, self.data)
        self._set_integration_state(state)

    def _integration_state(self):
        kind = mj.mjtState.mjSTATE_INTEGRATION
        state = np.empty(mj.mj_stateSize(self.model, kind))
        mj.mj_getState(self.model, self.data, state, kind)
        return state

    def _set_integration_state(self, state):
        kind = mj.mjtState.mjSTATE_INTEGRATION
        state = np.asarray(state, dtype=float)
        if (
            state.shape != (mj.mj_stateSize(self.model, kind),)
            or not np.isfinite(state).all()
        ):
            raise ValueError("Invalid shared MuJoCo integration state")
        mj.mj_setState(self.model, self.data, state, kind)
        mj.mj_forward(self.model, self.data)
        mj.mj_setState(self.model, self.data, state, kind)

    def _sync_adapter(self, boat_id):
        craft = self.crafts[boat_id]
        mapping = self.mappings[boat_id]
        d = craft.data
        for oq, sq, nq, ov, sv, nv in mapping["joints"]:
            d.qpos[oq : oq + nq] = self.data.qpos[sq : sq + nq]
            d.qvel[ov : ov + nv] = self.data.qvel[sv : sv + nv]
        d.time = self.data.time
        mj.mj_forward(craft.model, d)

    def _pose(self, boat_id):
        bid = self.mappings[boat_id]["bid"]
        r = self.data.xmat[bid].reshape(3, 3)
        v = np.zeros(6)
        mj.mj_objectVelocity(self.model, self.data, mj.mjtObj.mjOBJ_BODY, bid, v, 0)
        return self.data.xpos[bid].copy(), math.atan2(r[1, 0], r[0, 0]), v

    def _require(self, boat_id):
        if boat_id not in self.crafts:
            raise ValueError("Unknown vessel identity; current fleet retained")

    def _event(self, event, **values):
        self.events.append(dict(t_s=float(self.data.time), event=event, **values))
        self.events = self.events[-256:]

    def select(self, craft_id):
        with self._lock:
            self._require(craft_id)
            self.selectedId = craft_id
            return dict(ok=True, selectedId=craft_id)

    def action(self, craft_id, command):
        from .ricochet.plant import RICOCHET_SURFACE_LIMITS

        with self._lock:
            self._require(craft_id)
            if not isinstance(command, dict) or set(command) - set(
                RICOCHET_SURFACE_LIMITS
            ):
                raise ValueError("Unknown harbour control channel")
            for key, value in command.items():
                limits = RICOCHET_SURFACE_LIMITS[key]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (float, int))
                    or not math.isfinite(value)
                    or not limits["min"] <= value <= limits["max"]
                ):
                    raise ValueError("Invalid harbour control " + key)
            if craft_id in self.moorings and command.get("throttle", 0) > 0.02:
                raise ValueError("Release the berth before applying propulsion")
            self.crafts[craft_id].set_command(command)
            self._event("command", craft_id=craft_id, command=deepcopy(command))
            return dict(ok=True)

    def dock(self, craft_id, berth_id):
        with self._lock:
            self._require(craft_id)
            berth = self.berths.get(berth_id)
            if berth is None:
                raise ValueError("Unknown berth")
            if berth_id in self.occupancy and self.occupancy[berth_id] != craft_id:
                return dict(ok=False, reason="Berth occupied; reservation retained")
            if craft_id in self.moorings:
                return dict(ok=False, reason="Vessel already moored; release it first")
            craft = self.crafts[craft_id]
            p, h, v = self._pose(craft_id)
            target = np.asarray(self.world.to_world([berth["x"], berth["y"]]))
            if craft.variant not in berth["compatibleProfileIds"]:
                return dict(ok=False, reason="Vessel does not fit this berth")
            if np.linalg.norm(p[:2] - target) > 2.0:
                return dict(ok=False, reason="Move within 2 m of the berth centre")
            if np.linalg.norm(v[3:5]) > 0.5:
                return dict(ok=False, reason="Slow below 0.5 m/s before mooring")
            angle = math.atan2(
                math.sin(h + berth["heading"]), math.cos(h + berth["heading"])
            )
            if abs(angle) > math.radians(15):
                return dict(ok=False, reason="Align with the berth approach heading")
            if craft.command["throttle"] > 0.02:
                return dict(ok=False, reason="Set propulsion to idle before mooring")
            self.occupancy[berth_id] = craft_id
            self.moorings[craft_id] = dict(
                berth_id=berth_id, xy=p[:2].tolist(), heading=h
            )
            self._event("moored", craft_id=craft_id, berth_id=berth_id)
            return dict(ok=True, reason="Moored", berth_id=berth_id)

    def release(self, craft_id):
        with self._lock:
            self._require(craft_id)
            mooring = self.moorings.pop(craft_id, None)
            if mooring is None:
                return dict(ok=False, reason="Vessel is not moored")
            del self.occupancy[mooring["berth_id"]]
            self._event("released", craft_id=craft_id, berth_id=mooring["berth_id"])
            return dict(ok=True, reason="Released")

    def _moor_load(self, boat_id):
        if boat_id not in self.moorings:
            return np.zeros(3), np.zeros(3)
        p, h, v = self._pose(boat_id)
        moor = self.moorings[boat_id]
        force = np.r_[
            np.clip(
                1200 * (np.asarray(moor["xy"]) - p[:2]) - 1400 * v[3:5], -2500, 2500
            ),
            0.0,
        ]
        angle = math.atan2(math.sin(moor["heading"] - h), math.cos(moor["heading"] - h))
        return force, np.array(
            [0.0, 0.0, np.clip(1500 * angle - 1300 * v[2], -1800, 1800)]
        )

    def step(self, dt=DT):
        if not math.isfinite(dt) or abs(dt - DT) > 1e-12:
            raise ValueError(
                "Harbour rigid-body timestep is fixed at 100 Hz; aircraft remain at 400 Hz"
            )
        with self._lock:
            if self._interrupted_step:
                raise ValueError(
                    "Harbour step was interrupted; restore a complete checkpoint"
                )
            self._interrupted_step = True
            self.data.qfrc_applied[:] = 0.0
            self.data.xfrc_applied[:] = 0.0
            for boat_id, craft in self.crafts.items():
                self._sync_adapter(boat_id)
                mapping = self.mappings[boat_id]
                d = craft.data
                d.qfrc_applied[:] = 0.0
                d.xfrc_applied[:] = 0.0
                craft._slew_targets(DT)
                r = d.xmat[craft.bids["airframe"]].reshape(3, 3)
                v = np.zeros(6)
                mj.mj_objectVelocity(
                    craft.model, d, mj.mjtObj.mjOBJ_BODY, craft.bids["airframe"], v, 0
                )
                craft._apply_actuator_controls(float((r.T @ (v[3:] - craft.wind))[0]))
                force, torque = craft._compute_aero_and_propulsion()
                mf, mt = self._moor_load(boat_id)
                force = force + mf
                torque = torque + mt
                craft._last_ext_force_m = force.copy()
                craft._last_ext_torque_m = torque.copy()
                craft._evaluate_and_cache_hydro(
                    t=float(self.data.time),
                    force_eval=craft.step_count == 0,
                    ext_force_m=force,
                    ext_torque_m=torque,
                    update_stride_state=True,
                )
                # Predict the current microstep midpoint from the two most
                # recent actual samples. The old prev-to-current interpolation
                # added a whole-sample delay and injected roll energy at 20 Hz.
                # Constant/initial history stays constant; the interval mean is
                # the causal Adams-Bashforth weights (3/2,-1/2), without damping.
                phase = (
                    craft.step_count % craft.hydro_stride + 0.5
                ) / craft.hydro_stride
                for bid, current in craft._curr_hydro_f.items():
                    wrench = current + phase * (
                        current - craft._prev_hydro_f.get(bid, current)
                    )
                    self.data.xfrc_applied[mapping["bodies"][bid]] += np.clip(
                        wrench, -8e4, 8e4
                    )
                self.data.xfrc_applied[mapping["bid"], :3] += force
                self.data.xfrc_applied[mapping["bid"], 3:] += torque
                for oq, sq, nq, ov, sv, nv in mapping["joints"]:
                    self.data.qfrc_applied[sv : sv + nv] += d.qfrc_applied[ov : ov + nv]
                for old, new in mapping["actuators"].items():
                    self.data.ctrl[new] = d.ctrl[old]
            mj.mj_step(self.model, self.data)
            self.water.step(DT)
            mj.mj_forward(self.model, self.data)
            masses_changed = False
            for boat_id, craft in self.crafts.items():
                self._sync_adapter(boat_id)
                craft.step_count += 1
                power = float(craft.power.get("total_w", 0))
                burn = power * 1.15e-7
                craft.fuel[0] = max(0.0, float(craft.fuel[0]) - burn * DT)
                consumed = (
                    float(craft.energy.get("consumed_kwh", 0)) + power * DT / 3600000
                )
                craft.energy.update(
                    consumed_kwh=round(consumed, 6),
                    remaining_kwh=round(max(0.0, 20 - consumed), 6),
                    fuel_burn_kg_s=round(burn, 6),
                )
                craft.flags.discard("FUEL_EXHAUSTED")
                if craft.fuel[0] <= 1e-4:
                    craft.flags.add("FUEL_EXHAUSTED")
                p, h, v = self._pose(boat_id)
                hydro = craft.last_hydro
                if hydro is not None:
                    self.water.apply_for(
                        boat_id,
                        x=float(p[0]),
                        y=float(p[1]),
                        heading_rad=h,
                        vx_world=float(v[3]),
                        vy_world=float(v[4]),
                        heave_rate_mps=float(v[5]),
                        draft_m=float(hydro.draft_m),
                        submerged_vol_m3=float(hydro.submerged_volume_m3),
                        hydro_reaction_xy=tuple(
                            (
                                hydro.resistance_force_world
                                + hydro.dynamic_lift_force_world
                                + hydro.damping_force_world
                            )[:2]
                        ),
                        fan_thrust_n=float(sum(craft.last_thrust_per_fan_n)),
                        dt=DT,
                        t_s=float(self.data.time),
                    )
                before = craft._mass_version
                craft._update_bilge_flooding(
                    DT, craft.data.xmat[craft.bids["airframe"]].reshape(3, 3)
                )
                masses_changed |= before != craft._mass_version
                craft.max_alt = max(craft.max_alt, float(p[2]))
                craft._hydro_snapshot_dirty = False
            for ci in range(self.data.ncon):
                contact = self.data.contact[ci]
                force = np.zeros(6)
                mj.mj_contactForce(self.model, self.data, ci, force)
                magnitude = float(np.linalg.norm(force[:3]))
                for boat_id, craft in self.crafts.items():
                    if (
                        contact.geom1 in self.mappings[boat_id]["gids"]
                        or contact.geom2 in self.mappings[boat_id]["gids"]
                    ):
                        craft.max_impact_n = max(craft.max_impact_n, magnitude)
                        if magnitude > 1e5 and not craft.crashed:
                            craft.crashed = True
                            craft.flags.add("IMPACT")
                            self._event("impact", craft_id=boat_id, force_n=magnitude)
            if masses_changed:
                self._copy_masses()
            self.step_count += 1
            if (
                not np.isfinite(self.data.qpos).all()
                or not np.isfinite(self.data.qvel).all()
            ):
                raise FloatingPointError(
                    "Non-finite harbour state; retain checkpoint and inspect"
                )
            self._interrupted_step = False

    def visual_geometry(self, craft_id):
        with self._lock:
            self._require(craft_id)
            if craft_id not in self._geometry:
                self._geometry[craft_id] = self.crafts[craft_id].visual_geometry()
            return deepcopy(self._geometry[craft_id])

    def public(self):
        with self._lock:
            boats = []
            for definition in self.definitions:
                boat_id = definition["id"]
                craft = self.crafts[boat_id]
                p, h, v = self._pose(boat_id)
                poses = {
                    name: dict(
                        position=self.data.xpos[
                            self.mappings[boat_id]["bodies"][old]
                        ].tolist(),
                        quaternion_wxyz=self.data.xquat[
                            self.mappings[boat_id]["bodies"][old]
                        ].tolist(),
                    )
                    for name, old in craft.bids.items()
                }
                boats.append(
                    dict(
                        id=boat_id,
                        name=definition["name"],
                        variant=craft.variant,
                        position=p.tolist(),
                        heading_rad=h,
                        speed_mps=float(np.linalg.norm(v[3:5])),
                        command=deepcopy(craft.command),
                        dockedAt=(self.moorings.get(boat_id) or {}).get("berth_id"),
                        body_poses=poses,
                        configuration=dict(
                            hull_variant=craft.hull_bundle.variant_id,
                            geometry_sha256=craft.hull_bundle.main_hull.mesh.geometry_sha256,
                            model_xml_sha256=craft.provenance["model_xml_sha256"],
                        ),
                        crashed=craft.crashed,
                        flags=sorted(craft.flags),
                        fuel_kg=float(craft.fuel[0]),
                    )
                )
            berths = [
                dict(
                    b,
                    world_position=[
                        *self.world.to_world([b["x"], b["y"]]),
                        self.water.config.water_level_m,
                    ],
                    world_heading_rad=-b["heading"],
                    occupiedBy=self.occupancy.get(b["id"]),
                )
                for b in self.berths.values()
            ]
            return dict(
                available=True,
                schema="vtx-harbour-fleet-public-v1",
                t_s=float(self.data.time),
                selectedId=self.selectedId,
                boats=boats,
                berths=berths,
                occupancy=deepcopy(self.occupancy),
                events=deepcopy(self.events[-16:]),
                structures=deepcopy(self.world.structures),
                water_level_m=self.water.config.water_level_m,
                physics=dict(
                    rigid_body_hz=100,
                    hydrodynamic_hz=20,
                    shallow_water_hz=10,
                    dynamics_id=self.dynamics_id,
                    water_grid=deepcopy(self.water.grid_identity),
                    water_domain="shared polygon-masked airport basin",
                    aircraft_collision_coupling=False,
                ),
            )

    def serialize(self):
        with self._lock:
            self._validate_clocks()
            boats = {}
            for boat_id, craft in self.crafts.items():
                water = craft.water_field
                craft.water_field = _WaterReference(water)
                try:
                    native = craft.checkpoint_state()
                finally:
                    craft.water_field = water
                hydro = craft.last_hydro
                cache = (
                    None
                    if hydro is None
                    else dict(
                        values=_pack(
                            {f.name: getattr(hydro, f.name) for f in fields(hydro)}
                        ),
                        am_data=_pack(getattr(hydro, "_am_data", None)),
                    )
                )
                boats[boat_id] = dict(
                    native=native,
                    hydro=cache,
                    mass_version=craft._mass_version,
                    hydro_stride=craft.hydro_stride,
                )
            state = dict(
                schema=SCHEMA,
                cadence=deepcopy(CADENCE),
                dynamics_id=self.dynamics_id,
                step_count=self.step_count,
                world_sha256=self.world_sha256,
                dependencies_sha256=self.dependencies_sha256,
                model_xml_sha256=self.model_xml_sha256,
                mujoco_version=mj.__version__,
                definitions=deepcopy(self.definitions),
                selectedId=self.selectedId,
                boats=boats,
                integration=self._integration_state().tolist(),
                water=self.water.checkpoint_state(),
                moorings=deepcopy(self.moorings),
                occupancy=deepcopy(self.occupancy),
                events=deepcopy(self.events),
            )
            json.dumps(state, allow_nan=False)
            return state

    @classmethod
    def restore(cls, world, state):
        """Validate and restore into a fresh object; caller publishes only success."""
        from .harbour_water import HarbourWorld
        from .water.hydrodynamics import HydroBreakdown

        if not isinstance(state, dict) or state.get("schema") != SCHEMA:
            raise ValueError(
                "Harbour checkpoint uses incompatible development dynamics; record retained without conversion"
            )
        json.dumps(state, allow_nan=False)
        if state.get("cadence") != CADENCE:
            raise ValueError("Harbour checkpoint dynamics cadence differs")
        if type(state.get("step_count")) is not int or state["step_count"] < 0:
            raise ValueError("Invalid harbour clock tick counter")
        if state.get("dependencies_sha256") != dependency_fingerprint():
            raise ValueError(
                "Harbour physics/assets differ from checkpoint; no substitution"
            )
        if state.get("world_sha256") != HarbourWorld(world).fingerprint:
            raise ValueError("Harbour environment differs from checkpoint")
        if state.get("mujoco_version") != mj.__version__:
            raise ValueError("Harbour MuJoCo version differs from checkpoint")
        result = cls(
            world,
            vessels=state["definitions"],
            water_config=state["water"]["native"]["config"],
        )
        if result.model_xml_sha256 != state.get("model_xml_sha256"):
            raise ValueError("Harbour shared model differs from checkpoint")
        if result.dynamics_id != state.get("dynamics_id"):
            raise ValueError("Harbour selected dynamics/grid identity differs")
        if (
            set(state["boats"]) != set(result.crafts)
            or state["selectedId"] not in result.crafts
        ):
            raise ValueError("Checkpoint vessel identities differ")
        result.water.restore_state(state["water"])
        for boat_id, craft in result.crafts.items():
            saved = state["boats"][boat_id]
            if (
                saved["native"]["variant"] != craft.variant
                or saved["native"]["model_xml_sha256"]
                != craft.provenance["model_xml_sha256"]
            ):
                raise ValueError("Checkpoint boat model identity differs")
            from .ricochet.plant import RICOCHET_SURFACE_LIMITS

            for channel_set in ("command", "targets"):
                commands = saved["native"].get(channel_set)
                if not isinstance(commands, dict) or set(commands) != set(
                    RICOCHET_SURFACE_LIMITS
                ):
                    raise ValueError("Invalid saved vessel controls")
                for key, value in commands.items():
                    limit = RICOCHET_SURFACE_LIMITS[key]
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not limit["min"] <= value <= limit["max"]
                    ):
                        raise ValueError("Invalid saved vessel control " + key)
            if (
                type(saved["native"].get("step_count")) is not int
                or saved["native"]["step_count"] < 0
                or type(saved["mass_version"]) is not int
            ):
                raise ValueError("Invalid vessel integration counter")
            for channel_set in ("_curr_hydro_f", "_prev_hydro_f"):
                for body_id, wrench in saved["native"].get(channel_set, {}).items():
                    if int(body_id) not in craft.bids.values() or np.asarray(
                        wrench
                    ).shape != (6,):
                        raise ValueError("Invalid vessel hydrodynamic force buffer")
            water = craft.water_field
            craft.water_field = _WaterReference(water)
            try:
                craft.restore_state(saved["native"])
            finally:
                craft.water_field = water
            if saved["hydro"] is not None:
                hydro = HydroBreakdown(**_unpack(saved["hydro"]["values"]))
                for field in fields(hydro):
                    value = getattr(hydro, field.name)
                    if isinstance(value, np.ndarray):
                        if value.shape != (3,) or not np.isfinite(value).all():
                            raise ValueError(
                                "Invalid saved hydrodynamic vector " + field.name
                            )
                    elif field.name != "component_loads" and (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                    ):
                        raise ValueError(
                            "Invalid saved hydrodynamic scalar " + field.name
                        )
                if saved["hydro"]["am_data"] is not None:
                    hydro._am_data = _unpack(saved["hydro"]["am_data"])
                craft.last_hydro = hydro
            craft._mass_version = int(saved["mass_version"])
            craft.hydro_stride = int(saved["hydro_stride"])
            craft._raw_hydro_cache = None
            if craft.hydro_stride != HYDRO_STRIDE:
                raise ValueError("Checkpoint hydro stride differs")
        result._copy_masses()
        result._set_integration_state(state["integration"])
        moors = deepcopy(state["moorings"])
        occupancy = deepcopy(state["occupancy"])
        if set(moors) - set(result.crafts) or set(occupancy) - set(result.berths):
            raise ValueError("Unknown checkpoint berth/vessel claim")
        if len(set(occupancy.values())) != len(occupancy) or any(
            bid not in result.crafts for bid in occupancy.values()
        ):
            raise ValueError("Duplicate or unknown berth occupant")
        for boat_id, mooring in moors.items():
            if not isinstance(mooring, dict) or set(mooring) != set(
                ("berth_id", "xy", "heading")
            ):
                raise ValueError("Invalid checkpoint mooring")
            if occupancy.get(mooring["berth_id"]) != boat_id or np.asarray(
                mooring["xy"]
            ).shape != (2,):
                raise ValueError("Inconsistent checkpoint mooring ownership")
            if any(
                isinstance(v, bool) or not isinstance(v, (int, float))
                for v in [*mooring["xy"], mooring["heading"]]
            ):
                raise ValueError("Invalid checkpoint mooring pose")
            berth = result.berths[mooring["berth_id"]]
            if (
                result.crafts[boat_id].variant not in berth["compatibleProfileIds"]
                or np.linalg.norm(
                    np.asarray(mooring["xy"])
                    - result.world.to_world([berth["x"], berth["y"]])
                )
                > 2.000001
            ):
                raise ValueError("Checkpoint mooring does not match its berth")
        if set(occupancy.values()) != set(moors):
            raise ValueError("Checkpoint occupancy lacks mooring")
        if set(result.water.wakes) - set(result.crafts):
            raise ValueError("Checkpoint wake belongs to unknown vessel")
        result.moorings = moors
        result.occupancy = occupancy
        result.selectedId = state["selectedId"]
        result.events = deepcopy(state["events"])
        result.step_count = state["step_count"]
        if not isinstance(result.events, list) or len(result.events) > 256:
            raise ValueError("Invalid harbour event history")
        if abs(float(result.data.time) - result.water.sim_time_s) > 1e-9:
            raise ValueError("Checkpoint boat and water clocks differ")
        if any(
            abs(c.data.time - result.data.time) > 1e-9 for c in result.crafts.values()
        ):
            raise ValueError("Checkpoint vessel clocks differ")
        result._validate_clocks()
        return result

    def _validate_clocks(self):
        """Refuse partial ticks or altered phase instead of publishing a bad save."""
        if self._interrupted_step:
            raise ValueError(
                "Harbour step was interrupted; restore a complete checkpoint"
            )
        t = float(self.data.time)
        tolerance = 1e-8 + 2e-9 * abs(t)
        if self.model.opt.timestep != DT or any(
            c.model.opt.timestep != DT or c.hydro_stride != HYDRO_STRIDE
            for c in self.crafts.values()
        ):
            raise ValueError("Harbour runtime cadence differs")
        if abs(t - self.step_count * DT) > tolerance or any(
            c.step_count != self.step_count or abs(c.data.time - t) > tolerance
            for c in self.crafts.values()
        ):
            raise ValueError(
                "Harbour checkpoint tick/time phase mismatch or interrupted step"
            )
        if (
            abs(self.water.swe_step_interval_s - CADENCE["swe_interval_s"]) > 1e-15
            or abs(self.water.sim_time_s - t) > tolerance
        ):
            raise ValueError("Harbour checkpoint shared water clock mismatch")
        if (
            abs(self.water.shallow.t + self.water._swe_accum_s - self.water.sim_time_s)
            > tolerance
        ):
            raise ValueError("Harbour checkpoint water integration phase mismatch")
        swe_stride = round(CADENCE["swe_interval_s"] / DT)
        expected_swe_t = (self.step_count // swe_stride) * CADENCE["swe_interval_s"]
        expected_accum = (self.step_count % swe_stride) * DT
        if (
            abs(self.water.shallow.t - expected_swe_t) > tolerance
            or abs(self.water._swe_accum_s - expected_accum) > tolerance
        ):
            raise ValueError("Harbour checkpoint water cadence phase differs")
