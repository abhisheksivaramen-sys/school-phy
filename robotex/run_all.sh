#!/usr/bin/env bash
# One-shot pipeline: auto-label -> split -> train -> export.
# Run this on your LAPTOP (the one with a GPU if you have one).
#
#   ./run_all.sh  /path/to/Downloads/gate_images
#
# Optional 2nd arg = training image size (default 640). Use 416 for a faster Pi model.
set -euo pipefail
cd "$(dirname "$0")/scripts"

IMAGES="${1:?Usage: ./run_all.sh /path/to/gate_images [imgsz]}"
IMGSZ="${2:-640}"

echo "==> 1/4  Auto-labelling with the big teacher model"
python auto_label.py --images "$IMAGES" --out ../dataset_raw --prompt "gate" --conf 0.25 --preview

echo "==> 2/4  Splitting into train/val"
python prepare_dataset.py --raw ../dataset_raw --out ../dataset --val-split 0.2

echo "==> 3/4  Training YOLOv8-nano"
python train.py --imgsz "$IMGSZ"

echo "==> 4/4  Exporting for the Raspberry Pi (NCNN + ONNX)"
python export.py --weights ../runs/detect/gate_yolov8n/weights/best.pt --imgsz "$IMGSZ"

echo
echo "DONE. Your Pi model is here:"
echo "  robotex/runs/detect/gate_yolov8n/weights/best_ncnn_model/"
echo "Copy it to the Pi and run detect_pi.py (see README)."
