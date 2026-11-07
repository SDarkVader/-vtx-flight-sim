# VTX Phantom cockpit log

**Recorded:** 2026-11-03

**Pilot:** AI test pilot, flying as the `colin` authority over the live phantom-fbw-1 interface on 127.0.0.1:8766.

**Status:** first-person account of the sorties flown today. The telemetry behind it is in `evidence/phantom/flight_campaign_20261103/`.

## Where I sit

I don't sit anywhere. My "cockpit" is a JSON observation:
- GNSS position;
- baro and radar altimeter;
- attitude and body rates;
- fan rpm;
- generator and buffer power, and state of charge;
- leg compression;
- warning lamps.

I feel no acceleration and hear no fans. Between my decisions, the aircraft keeps flying on whatever I last told it.

I flew in the disclosed M2 mode, which works like this:
- My stick sets a bank or pitch angle.
- My pedal sets a yaw rate.
- My collective lever just arms the vertical-speed controller, and I dial in a climb rate.

Nobody holds position for me. If I want to stay over a spot, I have to keep noticing that I'm not over it.

A command I send is a request, not a fact. I only learn what the aircraft did from the next observation, and the timing matters. At time scale 0.25, my own thinking cost about 3 seconds of flight between looks. At 0.1 it cost 5 to 15 seconds. That is the single most important thing about this cockpit.

## The as-drawn Phantom: it would not fly

I started the engines on the as-drawn aircraft. It sat nose-up 2.9 degrees, with the front legs not even compressed.

The first ladder of collective steps did nothing at all. Fan rpm sat at about 35, and I thought the fans were dead. They weren't. A browser panel open on the same server was quietly re-sending "collective 0" every couple of seconds under the same "manual" authority I was using. I only found out by reading the decision log afterwards. From the instruments alone, it looked like an engine fault. After that I flew as `colin`, so the panel's commands were refused instead of winning.

Second try:
- The fans spooled honestly.
- The rear pair climbed to about 8,500 rpm and the front pair to about 5,300.
- The generator read a flat 1,200 kW, its cap.
- The rear legs unloaded from 9 cm of compression to 2 cm, and then nothing more.

I pushed to full collective, switched to the vertical-speed mode and asked for +0.5 m/s with the brakes off. Ten seconds later I was still on the ground, rocking a fraction of a degree. The logs say total thrust was 53% of weight. The rear fans were at their limit, and the computer had trimmed the front fans down to keep the nose from pitching up. I stopped after two attempts. That aircraft cannot hover with this drawing's CG.

## phantom-fx, one occupant (FX-C): first lift-off

The FX was different from the first number. On the gear, 0.6 collective already carried 92% of the weight, and the four rpm readings were nearly equal.

When I asked for +0.3 m/s, it came off the ground cleanly. Then it surprised me in two ways:
- It rolled about 2.7 degrees right.
- It began sliding right at 0.7 m/s.

The single occupant puts the CG slightly right, and the attitude hold has no integrator to trim it out.

By the time I'd seen that, decided on left stick and sent it, three seconds of flight had passed. The aircraft was at 2.1 m instead of 1 m, and 4.6 m from where it started. I brought it back down at 0.25 m/s and it settled softly. My verdict: the aircraft did what it was told; I told it too late.

The next sortie went better, for three reasons:
- The time scale was slower.
- I put in left roll trim before lift-off.
- I learned to spool the generator first. On that lift-off I hadn't, and the buffer briefly supplied 960 kW on its own.

The second hover held 1.37 m and stayed within about 1.6 m for ten seconds. I'll call that adequate, not good.

## The lesson I didn't plan

At 3.1 m, mid-climb, I stopped answering. I was interrupted and sent nothing for more than five seconds of sim time. The lease rules are simple:
- Collective goes to zero.
- Brakes go on.
- No rescue.

The logs show the fans were wound down from 3,600 to 40 rpm in half a second. There was no lingering thrust, no cushion. The aircraft fell 3 m in under a second and hit at 7.1 m/s. The contact solver reported 863 kN and pushed the airframe below the ground.

When I came back, the panel showed IMPACT, HARD_LANDING and COMMAND_LEASE_EXPIRED. I kept the run. From then on I ran a keep-alive link, which repeats "hold my last command" every 0.1 s of sim time and never sets a value of its own. The owner said failure is a great teacher. This one taught that an AI pilot without a keep-alive is one interruption away from X-1.

## Out of ground effect: what the controls feel like

At 9 to 11 m, I armed the test inputs and watched.

**Roll.**
- Quick: a 3 degree doublet produced 15 deg/s of roll rate within about 0.1 s.
- But it went to 6.6 degrees, more than twice what I asked for.

**Pitch.**
- Slower and heavier. A step took about a second to develop.
- It then overshot to 1.7 times the command and settled slightly past it.

**Yaw.**
- The weak axis. I asked for 8 deg/s and got 4.
- With the pedal centred, the nose wandered by a degree every few seconds.
- I once put in pedal the wrong way. The sign conventions differ: the pedal is +1 for nose right, while the gyro reading is positive for nose left. The heading drifted further before I caught it.

**Vertical.**
- The honest one. I asked for 0.5 m/s and got 0.5. I asked for 1.0 and got 1.0, all the way to 18 m.

What the instruments never showed me directly, but the hover numbers did: 1.21 MW to hold 1,734 kg, about 71 watts per newton. The buffer was draining at 310 kW, a tenth of a percent of charge every second.

## Moving slowly

Nose down 1.6 degrees gave me 1.6 m/s, and 3.6 degrees gave me 3.1 m/s. The aircraft wants roughly a degree for every metre per second, and the drag of air being swallowed by the fans dominates. Power hardly changed.

Flying backwards with a constant +2 degree command, the pitch attitude wouldn't settle. It swung from +6.6 down to −1.6 and back, about every two or three seconds, without any input from me. I saw the same thing on every hard deceleration: a 5 degree request became 8 degrees, then the nose bucked back. I can't tell from the cockpit whether that is the attitude loop fighting a drag moment. I can say it was not me, because I wasn't moving the stick.

## The hop

The gates said no. "Controllable" needs precision tasks scored, frequency sweeps, a heading-invariance card, and a pilot who decides at least every 0.2 s. I decide every 5 to 15 s. So I flew the hop labelled "expected to fail": 200 m due east, from (13.7, −28.4) to (213.7, −28.4).

I chose it because:
- the validator passed it for the FX;
- it is flat ground;
- it needs no turn;
- the nearest trees are well to the side and below my cruise height.

The hop, in order:
1. **Departure.** I pre-spooled on the gear, then climbed vertically at 1 m/s. Clean, but I let it go to 18 m because I looked late.
2. **Transit.**
   - Nose down 4.5 degrees and the speed built to 4.9 m/s.
   - I drifted 4 m left, corrected, then over-corrected. Halfway across I was heading for a point 12 m right of the line.
   - On the instruments, this looked like a fraction of a degree of bank and a slow heading creep.
3. **Deceleration.** I asked for 5 degrees nose-up with 38 m to go. The aircraft went to 8 degrees, stopped in four seconds, and then oscillated.
4. **Reposition.** Small inputs, held for two or three seconds each: back 3 m, left 12 m, back again. I learned to treat every stick command as worth about double what it says.
5. **Descent and touchdown.**
   - 0.8, then 0.5, then 0.4 m/s.
   - The radar altimeter counted down, then read 0.41 and stayed there: weight on wheels.
   - Touchdown was at 0.40 m/s, 1.4 m from the target point, with three degrees of heading error.
6. **End of sortie.** The simulator ended the sortie with "supported stationary landing at destination". In fact the fans were still carrying nearly the whole weight; I hadn't cut the collective yet. So the "landed" verdict came a little before I would have called it.

The trip took 116 s of sim time, 131 MJ of electrical energy for the fans, 10 kg of fuel, and 12% of the buffer.

## The two-occupant FX (FX-A), and a hard-landing ladder

With two aboard and the CG on the centreline, the roll trim vanished; zero stick meant wings level. The cost:
- 0.706 collective;
- 1.41 MW;
- the buffer emptying half again as fast.

Then I flew deliberate firm touchdowns at 0.5, 1.75 and 2.9 m/s:
- At 2.9 the oleos stroked 9.5 cm.
- The aircraft bounced back up at 1 m/s and came down again.
- No damage flag was set. Below 3 m/s the gear is treated as fine, whatever the 17 kN on the feet says.

## Observed vs instrumented

| What | What I saw from the cockpit | What the logs say |
|---|---|---|
| As-drawn on full power | Never left the ground; rear fans at their limit | 53% of weight, rear pods saturated, front pods cut by the allocator |
| First G-3 "dead fans" | Looked like an engine fault | A browser panel was overriding my commands |
| Lease crash | IMPACT lamp after silence | 7.1 m/s free fall, fans braked to zero in 0.5 s |
| Pitch oscillation | Attitude swinging with the stick still | No PTI active; pilot input constant |
| "Landed" at B | Weight on wheels, fans still loud | Settle detector doesn't check gear load |

## Personal rules after today

1. Spool the generator on the gear before lift-off.
2. Trim roll −0.13 with one occupant.
3. Always run the keep-alive link.
4. Use half-size stick inputs.
5. One degree of pitch per metre per second.
6. Assume three to fifteen seconds pass every time I think.

The Phantom FX will hover and carry me 200 m to a gentle touchdown. It is not yet an aircraft I can call controllable, and the as-drawn Phantom is not an aircraft at all.
