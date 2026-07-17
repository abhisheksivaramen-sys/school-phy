#!/usr/bin/env python3
"""
Step 3 — Train YOLOv8-nano on your gate dataset.

Nano (yolov8n) is the right size for a Raspberry Pi 4B: small and fast enough
to run in real time after NCNN export, while still accurate for a single class.

Usage
-----
    python train.py                       # sensible defaults, GPU if available
    python train.py --epochs 150 --imgsz 640
    python train.py --device cpu          # force CPU (slow but works)

Output: runs/detect/gate_yolov8n/weights/best.pt  <-- this is your model.
"""
import argparse
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="../config/gate.yaml")
    p.add_argument("--model", default="yolov8n.pt",
                   help="Start from pretrained nano weights (transfer learning).")
    p.add_argument("--epochs", type=int, default=120)
    p.add_argument("--imgsz", type=int, default=640,
                   help="Training resolution. 640 is a good balance; drop to 416 "
                        "for a faster (slightly less accurate) Pi model.")
    p.add_argument("--batch", type=int, default=16,
                   help="Lower to 8 or 4 if you run out of GPU memory.")
    p.add_argument("--device", default=None,
                   help="'0' for first GPU, 'cpu' to force CPU. Auto if omitted.")
    p.add_argument("--name", default="gate_yolov8n")
    p.add_argument("--patience", type=int, default=30,
                   help="Early-stop if val doesn't improve for this many epochs.")
    return p.parse_args()


def main():
    args = parse_args()
    from ultralytics import YOLO

    data_path = Path(args.data).expanduser().resolve()
    if not data_path.exists():
        raise SystemExit(f"Config not found: {data_path} (run prepare_dataset.py first)")

    # Save runs in a fixed, predictable place (robotex/runs/detect/<name>),
    # regardless of which directory you launch from. Ultralytics otherwise
    # resolves the output dir in a way that depends on its global settings.
    project = (Path(__file__).resolve().parent.parent / "runs" / "detect")

    model = YOLO(args.model)
    result = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(project),
        name=args.name,
        exist_ok=True,
        patience=args.patience,
        # Augmentations that help a competition model generalise to changing
        # light / angles on the course:
        hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
        degrees=5.0, translate=0.1, scale=0.5,
        fliplr=0.5, mosaic=1.0, close_mosaic=10,
        plots=True,
    )

    best = Path(result.save_dir) / "weights" / "best.pt"
    print("\nTraining complete.")
    print(f"  Best weights: {best}")
    print("  Validate visually: yolo predict model=<best.pt> source=<some_val_images>")
    print(f"  Next: python export.py --weights {best}")


if __name__ == "__main__":
    main()
