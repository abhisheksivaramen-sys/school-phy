#!/usr/bin/env python3
"""
Step 4 — Export the trained model to a format the Raspberry Pi 4B runs fast.

The Pi 4B has no GPU, so we export to NCNN (Tencent's ARM-CPU inference engine).
NCNN is the fastest option for YOLOv8 on a Pi 4 by a wide margin. ONNX is also
produced as a portable fallback.

Usage
-----
    python export.py --weights runs/detect/gate_yolov8n/weights/best.pt
    python export.py --weights best.pt --imgsz 416   # smaller = faster on Pi
"""
import argparse
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--weights", required=True, help="Path to best.pt from training.")
    p.add_argument("--imgsz", type=int, default=640,
                   help="Export resolution. Use the SAME value you'll run on the Pi. "
                        "416 or 320 gives a big speedup with modest accuracy loss.")
    p.add_argument("--formats", default="ncnn,onnx",
                   help="Comma-separated: ncnn (fastest on Pi), onnx (portable).")
    return p.parse_args()


def main():
    args = parse_args()
    from ultralytics import YOLO

    wp = Path(args.weights).expanduser()
    if not wp.exists():
        raise SystemExit(f"Weights not found: {wp}")
    model = YOLO(str(wp))

    for fmt in (f.strip() for f in args.formats.split(",") if f.strip()):
        print(f"\nExporting to {fmt} @ imgsz={args.imgsz} ...")
        out = model.export(format=fmt, imgsz=args.imgsz, half=False)
        print(f"  -> {out}")

    print("\nExport complete. Copy the exported model to the Raspberry Pi, e.g.:")
    print(f"  scp -r {wp.parent}/best_ncnn_model  pi@<pi-ip>:~/robotex/")
    print("Then run detect_pi.py on the Pi.")


if __name__ == "__main__":
    main()
