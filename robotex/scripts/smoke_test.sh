#!/usr/bin/env bash
# Prove the whole pipeline runs end-to-end on synthetic data.
# This does NOT produce a competition model — it verifies the scripts work,
# the models download, training runs, and NCNN export succeeds.
#
#   ./smoke_test.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Generate synthetic labelled gate images"
python make_test_images.py --out ../smoke_raw --n 16 --labels

echo "==> Split into train/val"
python prepare_dataset.py --raw ../smoke_raw --out ../smoke_dataset --val-split 0.25 \
    --config ../config/gate.yaml

echo "==> Train YOLOv8-nano (tiny run: 3 epochs, imgsz 320)"
python train.py --epochs 3 --imgsz 320 --batch 8 --device cpu --name smoke_gate

echo "==> Export to NCNN + ONNX"
python export.py --weights runs/detect/smoke_gate/weights/best.pt --imgsz 320

echo
echo "SMOKE TEST PASSED — pipeline runs end to end and exports a Pi model."
