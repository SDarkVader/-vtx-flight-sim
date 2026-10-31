# VTX: live fly-by-wire piloting contract

## Purpose

**Colin must actually pilot the aircraft.** A flight is a live sequence of observations, decisions and *control inputs* through a fly-by-wire interface. The user supplies departure point A and destination B, not a precomputed route. The plane is not animated along a waypoint spline, not teleported and not commanded directly by desired future positions.

Fly-by-wire describes the electronic link between pilot controls and modeled actuators. It does not mean an autonomous autopilot, and it does not override mass, gravity, angular momentum, inertia, gearbox constraints, rotor spool time, tilt rate or aerodynamic forces. The authoritative physics/research baseline is [PHYSICS_AND_RESEARCH_BASELINE.md](PHYSICS_AND_RESEARCH_BASELINE.md).

## Pilot and airframe are separate

- **Airframe:** the one mechanical VTX, with real mass/inertia, independent ducted fan actuation, ground contact, gravity, rotor gyroscopic and reaction dynamics, power limitations and collisions.
- **Fly-by-wire:** expose the physical control interface (e.g. lift/collective, pitch, roll, yaw, thrust-vector selection/tilt or sufficiently explicit per-nacelle commands) as consistent, continuously adjustable commands. Model command transport, actuator limits, lag, rate and feedback. Log *requested* versus *achieved* actuator states. A disclosed control allocator or limited augmentation is allowed as a physical part of the fly-by-wire system, but a flight-perfect autopilot, invisible stabilizer and direct pose/velocity/force injection are forbidden.
- **Colin, the pilot:** at each decision opportunity Colin receives only permitted observations (instrument readings, view/camera and map information actually available to the pilot), chooses an action, sends it to the **same flight-control interface used by a human operator**, observes what the aircraft did and decides again. Colin cannot read privileged simulator truth, issue physics-engine commands, call teleport/setPose, suppress a crash or decide that a scripted path has succeeded. The pilot is an agent *using* the controls, not a deterministic trajectory generator that already knows the answer.
- **Proprietor:** selects the initial valid departure position and the desired destination. That sets mission intent and spawn-on-ground only. No path, turns, tilt commands, route controller or manoeuvres are supplied.

## Required live operating loop

1. Show aircraft parked on its real landing gear at the chosen departure location; instruments and local visibility reflect the world.
2. At each time step, integrate the physics and actuator response independently of the pilot's decision rate. Gravity and rotational/angular-momentum effects apply even while Colin hesitates. Real-time view shows the current result.
3. Colin explicitly operates the engine/power and flight controls to attempt lift-off. He must adjust based on sensor feedback, including failed or partial lift, rotor spool lag, tilt coupling, roll/yaw error and ground contacts.
4. Colin pilots to B using observations, choosing heading, speed, height, obstacle avoidance and corrections as the situation develops. The destination is an objective, **not a path-following command**.
5. Colin flies the descent and touchdown using the same controls. If he misjudges, runs out of control authority or strikes terrain/obstacles, the simulation produces the actual failure. No automatic rescue.
6. Preserve observations, timestamped pilot-issued controls, achieved rotor actuation, physics states, collisions, energy use, outcomes and **changes to Colin's learned policy** across attempts.

Control inputs must be actionable and frequent enough to control an unstable aircraft; choose and document the actual flight-control and pilot-action rates, zero-order-hold/failsafe behavior when no pilot action arrives, latency and coupling. A slow AI action interface may require substeps and limited control augmentation; state exactly which part Colin operates and which part is embedded in the flight-control hardware. Do not hide an autopilot behind an AI model.

## Flight UI and machine control

Provide a proper interactive 3D flight-test environment, a cockpit/instrument panel with physical flight controls, and a machine-readable action/observation interface **with identical semantics to the manual interface**. The coding agent Colin must be able to run flight attempts through this interface and witness changes in real-time, not simply generate input files that an offline player replays. Manual operator takeover/inspection can use the same channels; control authority must be visible, not duplicated.

An agent pilot can learn within/between sorties. Persist the learning model/checkpoint and individual trial logs. Test actual learning by varying physical states and map missions, not by claiming success from a pre-tuned position controller.

## What replay is—and is not

Replays and deterministic initial conditions are **for evidence and debugging after a real attempted flight**. Recorded controls may be replayed to reproduce a failure and compare airframe revisions, but **Colin must not fly by feeding predetermined time-indexed paths or recorded successful control traces**. A repeated fixed input trace does not count as a new learning/piloting trial. Path planners may provide navigational advice from observed maps, but never actuate the craft autonomously or substitute for Colin's ongoing control decisions.

Physics unit tests can use canned inputs to test conservation and actuator correctness; that is not a flight demonstration.

## Acceptance demonstration

Starting from a valid A chosen by the proprietor and destination B:

- Colin issues and updates **live pilot controls** to perform an actual takeoff, navigation and attempted landing.
- Show a synchronized live log of `observation → Colin's decision → issued fly-by-wire input → achieved actuator states → observed motion/consequence` for multiple decisions.
- Confirm no automatic precomputed movement, guided spline, scripted waypoint completion or direct simulator-state modification is involved.
- Show at least one genuine failure/incorrect input with consequential physics, and subsequent pilot behavior adaptation based on that observed result—not a concealed reset or arbitrary tuning of physical parameters.
- Retain Colin's learned state for the **later proprietor-provided, previously unseen Stage 2 environment**, with no advance inspection or training.

If Colin only constructs a numeric controller and 3D replay window, **the assignment has not been completed**.
