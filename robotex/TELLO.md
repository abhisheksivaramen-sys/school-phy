# DJI Tello — autonomous gate run (fast path)

Everything runs on your **laptop**. The Tello makes its own WiFi; your laptop
joins it and flies it. No Pixhawk, Mission Planner, MAVLink, Raspberry Pi, or
calibration involved.

## 1. Install (2 min)
```bash
cd robotex
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install djitellopy ultralytics opencv-python
```

## 2. Connect
- Power on the Tello. On your laptop WiFi, join the **`TELLO-XXXXXX`** network.
- (You lose internet while on Tello WiFi — that's normal.)

## 3. Pick a detection model
- **Fastest to *fly* well:** your trained nano (`--model best.pt`). Runs fast on CPU.
  Train it with `run_all.sh` (see `README.md`) on photos of the real gates.
- **No training, works now (needs a decent laptop/GPU):** open-vocabulary detector:
  `--world --prompt "gate"`. On a CPU-only laptop this is slow — fine to prove the
  idea, but train the nano for a smooth run.

## 4. GROUND TEST FIRST — never skip this
```bash
python scripts/tello_gate_run.py --model best.pt --no-fly
```
- It shows the Tello's video with gate boxes and prints the commands it *would*
  send — **but never takes off**. Walk a gate in front of the camera and confirm
  the box tracks it. Fix detection here, on the ground.

## 5. Fly it
Clear/netted area, video window focused so keys work:
```bash
python scripts/tello_gate_run.py --model best.pt --speed 25
```
**Keys (click the video window first):**
| key | action |
|-----|--------|
| `t` | take off |
| `l` | land |
| `s` | toggle autonomous steering (off = hover in place) |
| `SPACE` | **EMERGENCY stop** — cuts motors, drops it. Last resort. |
| `q` | land + quit |

How it flies: yaw + strafe to centre the nearest gate, move forward when lined
up, and when the gate fills enough of the frame it punches straight through, then
hunts for the next gate. It counts gates as it clears them.

## 6. Tune (a few tries)
| Symptom | Fix |
|---|---|
| Overshoots / wobbles side to side | lower `--kp-yaw` and `--kp-lr` |
| Too slow / hesitant | raise `--speed` a little |
| Misses the gate, drifts past | raise `--pass-area` (get closer before punching) |
| Clips the gate edge | raise `--pass-frames` a bit, keep `--speed` low |
| Flies over/under the gate | adjust `--kp-ud` |
| Doesn't find gates | check the `--no-fly` view; retrain on real gate photos, or lower `--conf` |

## Honest limits
- I can't flight-test this from the cloud — first flight is your careful ground
  test (`--no-fly`) then a low-`--speed` hop with your hand on `l`/`SPACE`.
- Tello video is WiFi, so the control loop runs ~5–15 FPS; keep speeds modest.
- Battery ~13 min max; it auto-lands under `--min-battery` (default 15%).
- One gate at a time by sight — it flies to whatever gate is biggest in view. For
  a fixed course order, fly it so the next gate is roughly ahead after each pass.
```
```
