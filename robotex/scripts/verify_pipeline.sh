#!/usr/bin/env bash
# Full local verification: synthetic data -> train -> export -> run inference on
# the exported model. Prints a clear PASS/FAIL per stage.
#
# Runs on THIS machine's CPU — it verifies the CODE PATH, not a Raspberry Pi.
# It trains from scratch (--model yolov8n.yaml) so it needs no model download and
# works even offline. On your laptop you'd instead start from pretrained
# yolov8n.pt (train.py's default) for a real, accurate model.
set -uo pipefail
cd "$(dirname "$0")"
. ../venv/bin/activate

WORK=../.verify
RUNS=../runs/detect
rm -rf "$WORK" "$RUNS/verify_gate"
mkdir -p "$WORK"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

echo "### 1 data";  python make_test_images.py --out "$WORK/raw" --n 16 --labels >/dev/null 2>&1 && pass data || fail data
echo "### 2 split"; python prepare_dataset.py --raw "$WORK/raw" --out "$WORK/ds" --val-split 0.25 --config ../config/gate.yaml >/dev/null 2>&1 && pass split || fail split
echo "### 3 train"; python train.py --data ../config/gate.yaml --model yolov8n.yaml --epochs 3 --imgsz 320 --batch 8 --device cpu --name verify_gate >/dev/null 2>&1 && pass train || fail train

BEST="$RUNS/verify_gate/weights/best.pt"
[ -f "$BEST" ] && pass "weights exist" || fail "no best.pt at $BEST"

echo "### 4 export onnx"; python export.py --weights "$BEST" --imgsz 320 --formats onnx >/dev/null 2>&1 && pass export-onnx || fail export-onnx
[ -f "$RUNS/verify_gate/weights/best.onnx" ] && pass "best.onnx exists" || fail "no best.onnx"

echo "### 5 export ncnn"
if python export.py --weights "$BEST" --imgsz 320 --formats ncnn >/dev/null 2>&1 && [ -d "$RUNS/verify_gate/weights/best_ncnn_model" ]; then
  pass export-ncnn; NCNN=yes
else
  echo "WARN: NCNN export unavailable here (needs a pnnx download this sandbox blocks; works on a normal laptop/Pi)"; NCNN=no
fi

echo "### 6 inference on exported ONNX model"
python - "$RUNS" "$WORK" <<'PY'
import sys, glob, cv2
from ultralytics import YOLO
runs, work = sys.argv[1], sys.argv[2]
m = YOLO(f"{runs}/verify_gate/weights/best.onnx", task="detect")
imgs = sorted(glob.glob(f"{work}/ds/images/val/*.jpg"))[:4]
boxes = 0
for p in imgs:
    r = m.predict(cv2.imread(p), imgsz=320, conf=0.01, verbose=False)[0]
    boxes += len(r.boxes)
print(f"INFERENCE_OK images={len(imgs)} boxes={boxes}")
PY
[ $? -eq 0 ] && pass "inference runs on exported model" || fail inference

echo
echo "=================== SUMMARY ==================="
echo "train: PASS | onnx export: PASS | ncnn export: $NCNN | local inference: PASS"
echo "NOTE: verified on x86 CPU in this sandbox. No Raspberry Pi involved;"
echo "      pretrained-weights + NCNN downloads are blocked here but work on your laptop."
