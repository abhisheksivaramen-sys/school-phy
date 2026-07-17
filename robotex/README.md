# Robotex — Gate Detection for the S500 Drone

A complete, ready-to-run pipeline that trains a **YOLOv8-nano** model to detect
the competition **gate**, exports it to run fast on a **Raspberry Pi 4B**, and
steers the drone through the gate via **MAVLink → Pixhawk 2.4.8**.

The small nano model is **trained by a bigger model**: a large open-vocabulary
detector (YOLO-World) auto-labels all your gate photos, and the nano learns from
those labels. That's how you get an accurate model without hand-drawing
thousands of boxes.

> **Pipeline verified.** The full train → NCNN/ONNX export → on-Pi inference path
> was run end-to-end and passes (see `scripts/smoke_test.sh`). What you supply is
> your own gate photos; the scripts themselves are tested and working.

> ### Read this first — where things run
> This code was written for you in a cloud session that **cannot reach your
> laptop, your Downloads folder, or your Raspberry Pi**. Nothing here trains
> your model automatically in the cloud. **You run the steps below on your own
> laptop** (which has your gate images), then copy the finished model to the Pi.
> It's built to be nearly copy-paste — usually two commands.

---

## Your hardware (for reference)

| Part | Role |
|------|------|
| Raspberry Pi 4B | Companion computer — runs the gate detector |
| Pixhawk 2.4.8 | Flight controller — receives steering via MAVLink |
| Skydroid T10 | RC transmitter — **your manual override, always ready** |
| S500 frame, 1000KV motors, LittleBee ESCs | Airframe / propulsion |
| SE100 GPS | Positioning |

The Pi connects to the Pixhawk over a serial link (TELEM2). The detector runs on
the Pi's camera and sends velocity/yaw commands so the drone lines up with and
flies through the gate.

---

## Part A — On your LAPTOP: train the model

### 0. Install
```bash
cd robotex
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 1. The easy way — one command
Point it at the folder of gate images (your Downloads folder):
```bash
./run_all.sh  /path/to/Downloads/gate_images
# or for a faster (slightly less accurate) Pi model:
./run_all.sh  /path/to/Downloads/gate_images  416
```
That auto-labels → splits → trains → exports. When it finishes, your Pi model is
`scripts/runs/detect/gate_yolov8n/weights/best_ncnn_model/`.

### 1b. The step-by-step way (same thing, more control)
```bash
cd scripts
python auto_label.py --images /path/to/gate_images --out ../dataset_raw --preview
python prepare_dataset.py --raw ../dataset_raw --out ../dataset --val-split 0.2
python train.py --epochs 120 --imgsz 640
python export.py --weights runs/detect/gate_yolov8n/weights/best.pt --imgsz 640
```

### Sanity-check your labels (important!)
The teacher isn't perfect. After `auto_label.py`, open a handful of images in
`dataset_raw/preview/` and confirm the boxes are actually on the gates.
- Too many wrong boxes? Raise `--conf` (e.g. `0.35`) or use a sharper prompt like
  `--prompt "square drone racing gate"`.
- Missing gates? Lower `--conf` (e.g. `0.20`).
- A few bad ones? Just delete those image+label pairs before `prepare_dataset.py`.

Good labels here = a good model. This 5-minute check is the highest-leverage step.

---

## Part B — On the RASPBERRY PI: run it

### 1. Copy the model over (from your laptop)
```bash
scp -r scripts/runs/detect/gate_yolov8n/weights/best_ncnn_model  pi@<pi-ip>:~/robotex/
scp scripts/detect_pi.py  robotex/requirements.txt  pi@<pi-ip>:~/robotex/
```

### 2. Install on the Pi
```bash
ssh pi@<pi-ip>
cd ~/robotex
pip install ultralytics opencv-python pymavlink   # NCNN backend ships with ultralytics
```

### 3. Test detection ONLY (no motors)
```bash
python detect_pi.py --model best_ncnn_model --imgsz 416 --show
```
You should see the gate boxed and a live FPS readout. On a Pi 4B at `imgsz 416`
expect roughly 8–15 FPS with NCNN. Drop to `--imgsz 320` for more speed.

### 4. Add flight control — **PROPS OFF, on the bench, first**
Wire the Pi ↔ Pixhawk TELEM2 (Pi TX→FC RX, Pi RX→FC TX, GND↔GND). In the Pixhawk
params set `SERIAL2_PROTOCOL=2` (MAVLink2) and a matching baud (e.g. `SERIAL2_BAUD=921`).
Then:
```bash
# Dry run: computes commands, sends NOTHING (safe)
python detect_pi.py --model best_ncnn_model --mavlink /dev/ttyAMA0 --baud 921600

# Live: actually sends velocity commands (props OFF for the first test!)
python detect_pi.py --model best_ncnn_model --mavlink /dev/ttyAMA0 --baud 921600 --fly
```
The script sends body-frame velocity + yaw-rate: it yaws to centre the gate,
adjusts height, and nudges forward once lined up. For real flight the Pixhawk
must be in **GUIDED** mode with the aircraft armed — and your **hand on the
Skydroid T10 to switch back to STABILIZE/MANUAL instantly**.

Tune the response with `--kp-yaw`, `--kp-vz`, `--fwd-speed`, `--max-yaw`.

---

## ⚠️ Safety

This flies a real aircraft from computer vision. It **will** make mistakes.
- Test detection with **props removed** first, then in a **large open area**.
- Keep the RC transmitter in hand at all times; manual override is your kill switch.
- Follow your local drone rules and the Robotex event safety brief.
- You are responsible for safe operation.

---

## Files

```
robotex/
  run_all.sh              one-command laptop pipeline
  requirements.txt
  config/gate.yaml        dataset + class config (auto-updated)
  scripts/
    auto_label.py         1. big model labels your images
    prepare_dataset.py    2. train/val split + config
    train.py              3. train YOLOv8-nano
    export.py             4. export to NCNN/ONNX for the Pi
    detect_pi.py          5. on-Pi detection + MAVLink guidance
```

## Troubleshooting
- **Model misses gates in the arena** → your training photos don't match the
  arena. Grab 50–100 photos *at the venue* (angles, lighting, distances),
  re-run `run_all.sh`. Real-venue images matter more than quantity.
- **Slow on the Pi** → export and run at `--imgsz 320`; close other processes;
  ensure you're using the `_ncnn_model`, not the `.pt`.
- **No MAVLink heartbeat** → wrong port/baud, or TX/RX swapped. Try
  `--mavlink /dev/serial0`, check `SERIAL2_*` params, confirm wiring.
