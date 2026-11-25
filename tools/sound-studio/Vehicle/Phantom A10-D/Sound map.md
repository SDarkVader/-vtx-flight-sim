# Phantom A10-D sound map (draft 1)

Nothing here is decided or in the game yet. Take lengths are measured; which take suits which part is from file names, not listening.

## Layers

| # | Sound | Type | Driven by (existing game signal) | Your takes |
|---|---|---|---|---|
| 1 | Wheel fans, x4 | loop | each fan's RPM: pitch and level | none |
| 2 | Boosters, x2 | loop | spool: pitch; thrust: level | none |
| 3 | Pod tilt | movement | pod joint speed | thruster pivot (3.3 s), wheel-thruster assembly (3.3 s) |
| 4 | Legs | movement | leg joint speed | geared motor (4.2 s) |
| 5 | Wings | movement | wing joint speed | wing deployment (6.1, 6.1, 10.0 s) |
| 6 | Flaps and stabilisers | movement | flap and stab joint speed | flap actuator (5.3 x3, 6.1, 12.6 s) |
| 7 | Air brake | movement | air brake amount | none |
| 8 | Wing latch | single hit | wing reaches locked or stowed | none |
| 9 | Touchdown | single hit | a foot or tyre makes contact | none |
| 10 | Tyres | loop | ground speed; slip adds scrub | none |
| 11 | Wind | loop | airspeed | none |
| 12 | Cockpit hum | loop | on while in cockpit | none |
| 13 | Radio | music | player's choice | your 15 tracks |

## How a moving part should sound

Three pieces: a start, a run that loops while the joint is moving, and a stop. The run follows the joint's speed, so the sound lasts exactly as long as the movement whatever the take length. Each take can be cut into these three.

## Mix rules (proposed)

- Fans and boosters lead. Mechanisms are clearest when the fans are quiet (on the ground).
- Cockpit: outside sounds are muffled, mechanisms come through the airframe, radio stays clear.
- Four fans are slightly detuned and placed left and right, so they don't sound like one fan.
- The radio dips briefly for touchdown and latches.

## Build order

1. Wings: you have three takes, and it proves the start / run / stop method.
2. Pods, legs, flaps with the same method.
3. Generate and fit fans and boosters (prompts are in "Firefly prompts to try.txt").
4. Single hits, tyres, wind, cockpit hum, radio.

Each step: you listen and approve before it goes into the game.

## Character (your choice): a mixture, because it's a video game

How I propose to split it; change anything:

| Grounded (follows the flight data closely) | Heightened (made to feel good) |
|---|---|
| Fan and booster pitch and level | Spool-up and booster kick get extra punch |
| Mechanisms last exactly as long as the movement | Every movement starts and ends with a clear clunk |
| Wind, tyres, tunnel and cockpit muffling | Latch lock-in and touchdown are bigger than life |
| Direction and distance | Wing transformation is a set-piece, briefly louder than its surroundings |

Rule: grounded sounds tell the player what the machine is doing; heightened ones reward what the player did.
