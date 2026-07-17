# Mission Planner First-Time Setup & Calibration — S500 / Pixhawk 2.4.8

Your hardware: **Pixhawk 2.4.8** (ArduCopter), **S500 quad frame**, **SE100 GPS+compass**,
**Skydroid T10** radio (SBUS), **LittleBee ESCs**, **1000KV motors**.

> ⚠️ **PROPELLERS OFF for every step below except the final flight.** Motor tests and
> ESC calibration spin the motors — bare motors only. Battery only connected when a
> step says so.

The red "PreArm" errors you see now are normal on a fresh board. Each calibration
step clears one of them. Do the steps **in this order** — order matters.

---

## Step 0 — Firmware & frame (do once)
1. Connect Pixhawk by USB. In Mission Planner top-right, pick the COM port + `115200`, click **Connect**.
2. **SETUP → Install Firmware** → choose **ArduCopter (Quad)**. Let it flash, reconnect.
3. **SETUP → Mandatory Hardware → Frame Type** → select **X** (S500 is a quad in X layout).

## Step 1 — Accelerometer (level) calibration
1. **SETUP → Mandatory Hardware → Accel Calibration → Calibrate Accel**.
2. Follow the prompts: place the board **level, on its right side, left side, nose down,
   nose up, on its back**, clicking to continue at each. Keep it dead still each time.
3. Also click **Calibrate Level** with the frame sitting flat.
   → clears `PreArm: 3D Accel calibration needed`.

## Step 2 — Compass calibration (your SE100 has the compass)
1. **SETUP → Mandatory Hardware → Compass**.
2. Use the external compass (the one in the SE100/GPS). Tick "use compass", make the
   **external** one Compass 1 / primary. Set its **orientation** (usually the arrow on the
   GPS points forward → Rotation `None`; if the module is mounted rotated, match it).
3. Click **Start** (Onboard/Live calibration), then **rotate the whole drone** slowly
   through every axis — spin it around all three axes like a slow tumble — until the bars
   fill and it says success. Reboot when asked.
   → clears `PreArm: Compass not calibrated` / `Compasses inconsistent`.
   - Move away from laptops, phones, speakers, rebar floors, and the battery's power wires
     during this — metal/magnets ruin compass cal.

## Step 3 — Radio calibration (Skydroid T10)
1. **Bind** the Skydroid T10 air unit to the transmitter first (per T10 manual), and wire
   its **SBUS** output to the Pixhawk **RCIN** port. Power the receiver.
2. **SETUP → Mandatory Hardware → Radio Calibration**. Turn on the T10.
3. You should see the green bars move when you move sticks. Click **Calibrate Radio**,
   then move **every stick and switch to its extremes**. Click **Done**.
   → clears `PreArm: RC not calibrated`.
   - No bars moving? RC protocol/wiring: confirm SBUS on RCIN. Check `RC_PROTOCOLS` = All (or SBUS),
     and that the T10 outputs SBUS (not PPM). Tell me and I'll help.

## Step 4 — Flight modes
1. **SETUP → Mandatory Hardware → Flight Modes**. Assign a switch on the T10 to select modes.
2. Good starter set: **Stabilize**, **AltHold**, **Loiter** (needs good GPS), and keep one
   position for **RTL** (Return to Launch). Set your kill/override the way you're used to.

## Step 5 — ESC calibration (LittleBee) — MOTORS BARE, NO PROPS
LittleBee are BLHeli ESCs. All-at-once calibration in ArduCopter:
1. Disconnect battery + USB. Set throttle stick to **max**.
2. Plug in the **battery** (still USB-disconnected). The board boots, LEDs cycle.
3. Wait for the ESC beeps, then pull throttle to **min**. You'll hear confirmation beeps.
4. Disconnect battery. Calibration stored.
   (Alternative: set `ESC_CALIBRATION`/param method — ask me if the stick method misbehaves.)

## Step 6 — Motor test: direction & wiring — NO PROPS
1. **SETUP → Optional Hardware → Motor Test** (or the SETUP → Motor Test screen).
2. Test each motor at ~5–10%. Mission Planner labels **A B C D** — check each spins and
   note direction. On an **X quad** the correct spin pattern (Betaflight-independent,
   ArduCopter numbering):
   - Motor 1 = front-right = **CCW**
   - Motor 2 = back-left = **CCW**
   - Motor 3 = front-left = **CW**
   - Motor 4 = back-right = **CW**
3. Wrong direction on a motor → swap **any two of its three** motor wires (or reverse it in
   BLHeliSuite). Wrong position → swap the ESC signal leads on the Pixhawk output rail.
4. Only after directions are correct: fit props so each matches its motor's rotation
   (CW motor → CW prop). **Props go on last.**

## Step 6.5 — MicoAir MTF-01 optical flow + rangefinder (CRITICAL for indoor Robotex)
The Robotex course is **indoor** (safety-netted, ~11×5×2.5 m) — **GPS will not lock
reliably indoors**, so the MTF-01 is what lets the drone hold position and fly a stable
line through the walls. Set it up before you try any position-holding flight.

**A. Configure the module itself (one time):**
Using MicoAir's **MicoAssistant** tool, set the MTF-01 output protocol to **`mav_apm`**.
Wire the MTF-01 to a serial port — these steps assume **TELEM2** (so `SERIAL2_*`). Mount it
**pointing straight down**, lens unobstructed, rigid (no foam that lets it wobble).

> **Which SERIALn is my MTF-01 on?** Map the physical port to the parameter prefix:
> TELEM1→`SERIAL1`, TELEM2→`SERIAL2`, GPS→`SERIAL3`, GPS2→`SERIAL4`, and so on.
> Your Mission Planner telemetry radio is usually on **TELEM1 (`SERIAL1`)**, so the MTF-01
> should go on **TELEM2 (`SERIAL2`)** — use the `SERIAL2_*` params below. Quick check:
> temporarily set that port's `SERIALn_PROTOCOL = 1` and see the flow data appear; if not,
> you picked the wrong `n`. Trace the JST cable from the module to the labelled FC port.

**B. Mission Planner parameters** (CONFIG → Full Parameter List). Assuming TELEM2:
```
SERIAL2_PROTOCOL = 1        # MAVLink
SERIAL2_BAUD     = 115       # 115200
SERIAL2_OPTIONS  = 1024      # don't forward
FLOW_TYPE        = 5         # MicoAir MTF-01
RNGFND1_TYPE     = 10        # MAVLink rangefinder (the MTF-01's laser)
```
Reboot, then set:
```
RNGFND1_MIN_CM   = 1
RNGFND1_MAX_CM   = 800       # MTF-01 laser ~8 m
RNGFND1_ORIENT   = 25        # downward
```

**C. EKF3 sources — use optical flow for indoor position (no GPS):**
```
AHRS_EKF_TYPE   = 3
EK3_SRC_OPTIONS = 0
EK3_SRC1_POSXY  = 0     # no GPS horizontal position
EK3_SRC1_VELXY  = 5     # optical flow horizontal velocity
EK3_SRC1_POSZ   = 2     # rangefinder for height
EK3_SRC1_VELZ   = 0
EK3_SRC1_YAW    = 1     # compass
```
(If you also want to fly outdoors on GPS, put those on `EK3_SRC2_*` and bind an RC switch,
e.g. RC6, to swap EKF source — ask me and I'll give the exact switch params.)

**D. Verify before flight:**
- CONFIG → **Sensors / Optical Flow** and the **Rangefinder** page: wave a hand under the
  sensor — the rangefinder distance should change; move the drone over a textured surface
  and the flow X/Y should react. A **plain, textured, well-lit floor** is essential — flow
  fails over blank/shiny/dark surfaces (that white 50 mm line + floor texture helps).
- Pre-arm should stop complaining about GPS for position modes once flow+rangefinder are healthy.

**E. Optical-flow calibration (quick):** hover in **AltHold** ~1 m over textured floor, gently
roll and pitch, and check the flow-vs-gyro match in the Optical Flow screen; adjust
`FLOW_FXSCALER` / `FLOW_FYSCALER` if the flow consistently reads high/low. Full procedure:
ArduPilot "MicoAir MTF-01" + "Optical Flow Sensor Testing and Setup" docs.

**Indoor flight modes that work with flow:** **AltHold** (rangefinder height), **Loiter** and
**PosHold** (flow position) once EKF is happy. **Do NOT rely on Loiter until the flow/rangefinder
check in D passes.** For the autonomous run, the gate-detection guidance in `detect_pi.py`
sends velocity commands on top of this stabilized platform.

## Step 6.7 — CH8 autonomous handover (the "one switch" you wanted, done safely)
A single switch cannot both auto-launch AND be manual at the same time — those are opposite
states, and auto-arming on a flip with no throttle in your hand causes flyaways. The safe
version that gives you what you actually want:

1. **CH8 arm switch (optional, manual flying):** set `RC8_OPTION = 153` if you want CH8 to
   arm/disarm for manual flights. (Skip if you use CH8 only for the Pi handover below.)
2. **CH8 → Pi takes over (autonomous gate run):** the Raspberry Pi watches CH8 and does the
   flying, so you keep instant override. Run on the Pi:
   ```bash
   python detect_pi.py --model best_ncnn_model --imgsz 416 \
       --mavlink /dev/serial0 --baud 921600 --fly --ch8-handover --takeoff-alt 1.2
   ```
   - **CH8 HIGH** → Pi sets **GUIDED**, arms if needed, climbs to `--takeoff-alt`, then steers
     through gates with the vision model.
   - **CH8 LOW** → Pi commands **LOITER** (holds position on optical flow) and stops guiding —
     you fly manually.
   - **Always:** move your own flight-mode switch out of GUIDED on the transmitter and
     ArduPilot hands control straight back to you. That is your override at all times.

   Requirements for GUIDED to be safe indoors: optical flow + rangefinder **healthy**
   (Step 6.5 verified), and `--fly` only after a props-off bench test of the whole sequence.

## Step 7 — Failsafes (do NOT skip on a competition drone)
- **SETUP → Failsafe**: set **Battery Failsafe** (low-voltage → RTL/Land), **Radio Failsafe**
  (signal loss → RTL), and confirm the T10's failsafe behaviour.
- Set battery capacity/voltage monitor if you have a power module.

## Step 8 — Final arming check
With props on, in a safe open area, all pre-arm errors cleared: the board should arm in
**Stabilize**. If it refuses, read me the exact `PreArm:` line — that names the one thing
still unsatisfied.

---

## Common PreArm errors → what they mean

| Error text | Fix |
|---|---|
| `3D Accel calibration needed` | Step 1 |
| `Compass not calibrated` / `Compasses inconsistent` | Step 2 (redo away from metal/magnets) |
| `RC not calibrated` | Step 3 |
| `Bad GPS Health` / `Need 3D Fix` | Take it **outside**, wait for satellites; indoors GPS won't lock. Loiter/Auto need this; Stabilize does not. |
| `Gyros inconsistent` / `Accels inconsistent` | Redo accel cal; if it persists on a 2.4.8 clone, tell me — may be a bad IMU. |
| `Baro not healthy` | Reboot; keep board out of wind/AC draft during boot. |
| `EKF ... variance` / `Waiting for Nav Checks` | Usually resolves after good compass + GPS; give it time outdoors, stationary. |
| `Hardware safety switch` | Press the physical safety button until solid, or set `BRD_SAFETY_DEFLT=0`. |

## Notes for your specific board
- The **Pixhawk 2.4.8** is a common clone — compass/baro can be finicky. Prefer the
  **external** SE100 compass over the internal one (Step 2).
- **LittleBee/BLHeli**: if MP's stick ESC cal is inconsistent, configuring endpoints in
  **BLHeliSuite** and skipping ArduCopter ESC cal is often more reliable — ask me.
- **Skydroid T10** is SBUS: RCIN port, `RC_PROTOCOLS` includes SBUS, receiver bound + powered.

---

**When you hit a wall:** copy the exact red text from the Mission Planner HUD or the
**Messages** tab and send it to me. I'll tell you the precise parameter or step to fix it.

---

## Robotex course — what you're building for

Robotex "Aviation Academy" drone race (beginner): an **autonomous** drone flies an
**indoor** obstacle course, roughly **11 m long × 5 m wide × 2.5 m high**, surrounded by a
**safety net**, with **4 walls the drone must fly through** and a **white ~50 mm line** on
the floor. (Confirm the exact numbers against *your* event's current rules PDF — they vary
by year/region.)

What this means for your build:
1. **Indoor = optical flow, not GPS.** Step 6.5 (MTF-01) is the single most important thing
   for a stable autonomous run. Get flow + rangefinder solid first.
2. **The "gates" are the wall openings.** The YOLOv8 gate model (see `README.md`) detects
   them; `detect_pi.py` steers the drone to centre and fly through — that's your autonomy.
   Train on photos of the **actual wall/gate design** used at your event.
3. **The white floor line** is a strong navigation cue. Two easy wins: (a) it gives the
   optical flow good texture to lock onto; (b) you can add a simple line-follow to keep the
   drone centred between gates — tell me if you want me to add a line-follow mode to
   `detect_pi.py`.
4. **Small arena, low ceiling.** Tune gentle speeds/gains (`--fwd-speed`, `--kp-yaw` in
   `detect_pi.py`) — there's little room to recover from an overshoot.

### Suggested build order
1. Mission Planner mandatory calibrations (Steps 0–5 above) — get it flying manually in Stabilize.
2. MTF-01 optical flow (Step 6.5) — get stable AltHold, then Loiter/PosHold indoors.
3. Failsafes (Step 7).
4. Train the gate model on real gate photos (`README.md` / `run_all.sh`).
5. Bench-test `detect_pi.py` detection (props off), then guided flights in the netted area.

Sources: [Robotex Aviation Academy Drone Race](https://robotex.international/aviation-academy-drone-race-for-beginners/) ·
[Robotex India beginner rules PDF](https://www.robotex-india.in/images/Aviation-Academy-Drone-Race-Beginner-Level-Rules-Robotex-International-2022-ENG.pdf) ·
[ArduPilot MTF-01 (Copter)](https://ardupilot.org/copter/docs/common-mtf-01.html)
