#!/usr/bin/env python3
"""
Step 1 — Auto-label your gate images with a BIG model (the teacher).

This is the "trained by a bigger model" part of your request. Instead of you
hand-drawing thousands of boxes, a large open-vocabulary detector (YOLO-World)
looks at every image and draws the gate boxes for you. Those boxes become the
training labels for the small YOLOv8-nano model that runs on the Pi.

Usage
-----
    python auto_label.py --images /path/to/your/Downloads/gate_images \
                         --out    ../dataset_raw \
                         --prompt "gate" \
                         --conf   0.25

Then eyeball a few labels (see README, "Sanity-check your labels") and move on
to prepare_dataset.py.

Notes
-----
* --prompt controls what the teacher looks for. If your gates are a specific
  colour/shape, a richer prompt helps, e.g. "red rectangular gate" or
  "square drone racing gate". You can pass several comma-separated prompts;
  every match is labelled as class 0 (gate).
* Lower --conf finds more gates but adds false boxes; higher is stricter.
  0.20–0.35 is a good starting range. Always review the output.
"""
import argparse
import os
from pathlib import Path

import cv2

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args():
    p = argparse.ArgumentParser(description="Auto-label gate images with YOLO-World.")
    p.add_argument("--images", required=True, help="Folder containing your gate photos.")
    p.add_argument("--out", default="../dataset_raw",
                   help="Output folder for images + YOLO-format .txt labels.")
    p.add_argument("--prompt", default="gate",
                   help="What the teacher looks for. Comma-separate multiple prompts.")
    p.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    p.add_argument("--model", default="yolov8x-worldv2.pt",
                   help="Teacher model. yolov8x-world = most accurate, "
                        "yolov8s-world = faster. Auto-downloaded on first run.")
    p.add_argument("--preview", action="store_true",
                   help="Also save annotated preview images so you can eyeball them.")
    return p.parse_args()


def main():
    args = parse_args()
    from ultralytics import YOLO  # imported here so --help works without the dep

    images_dir = Path(args.images).expanduser()
    out_dir = Path(args.out).expanduser()
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "labels").mkdir(parents=True, exist_ok=True)
    if args.preview:
        (out_dir / "preview").mkdir(parents=True, exist_ok=True)

    if not images_dir.is_dir():
        raise SystemExit(f"Image folder not found: {images_dir}")

    files = sorted(f for f in images_dir.rglob("*") if f.suffix.lower() in IMG_EXTS)
    if not files:
        raise SystemExit(f"No images found in {images_dir}")
    print(f"Found {len(files)} images. Loading teacher model '{args.model}'...")

    model = YOLO(args.model)
    classes = [c.strip() for c in args.prompt.split(",") if c.strip()]
    model.set_classes(classes)
    print(f"Teacher is looking for: {classes}")

    n_labeled, n_boxes, n_empty = 0, 0, 0
    for i, fp in enumerate(files, 1):
        img = cv2.imread(str(fp))
        if img is None:
            print(f"  ! skipped unreadable image: {fp.name}")
            continue
        h, w = img.shape[:2]

        res = model.predict(img, conf=args.conf, verbose=False)[0]
        lines = []
        for box in res.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            # convert to YOLO normalised cx,cy,w,h  (all class 0 = gate)
            cx = ((x1 + x2) / 2) / w
            cy = ((y1 + y2) / 2) / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            lines.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        stem = f"{i:05d}_{fp.stem}"
        cv2.imwrite(str(out_dir / "images" / f"{stem}.jpg"), img)
        (out_dir / "labels" / f"{stem}.txt").write_text("\n".join(lines))

        if lines:
            n_labeled += 1
            n_boxes += len(lines)
        else:
            n_empty += 1  # kept as a "background" negative example — that's fine

        if args.preview:
            cv2.imwrite(str(out_dir / "preview" / f"{stem}.jpg"), res.plot())

        if i % 25 == 0 or i == len(files):
            print(f"  [{i}/{len(files)}] labelled={n_labeled} boxes={n_boxes} empty={n_empty}")

    print("\nDone.")
    print(f"  images with >=1 gate : {n_labeled}")
    print(f"  total gate boxes     : {n_boxes}")
    print(f"  images with no gate  : {n_empty} (kept as negatives)")
    print(f"  output               : {out_dir.resolve()}")
    if args.preview:
        print(f"  previews             : {(out_dir / 'preview').resolve()}  <-- LOOK AT THESE")
    print("\nNext: python prepare_dataset.py --raw", out_dir)


if __name__ == "__main__":
    main()
