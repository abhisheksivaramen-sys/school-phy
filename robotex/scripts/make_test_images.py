#!/usr/bin/env python3
"""
Generate a few synthetic 'gate' images so the pipeline can be smoke-tested
without real data. NOT for a real competition model — just to prove the
scripts run end-to-end. Real gates come from your own photos.
"""
import argparse
from pathlib import Path

import cv2
import numpy as np


def make_one(w=640, h=480, seed=0):
    rng = np.random.RandomState(seed)
    img = rng.randint(60, 120, (h, w, 3), dtype=np.uint8)  # noisy background
    # a bright rectangular "gate" (hollow frame)
    gw, gh = rng.randint(120, 260), rng.randint(140, 300)
    cx, cy = rng.randint(gw // 2 + 10, w - gw // 2 - 10), rng.randint(gh // 2 + 10, h - gh // 2 - 10)
    x1, y1, x2, y2 = cx - gw // 2, cy - gh // 2, cx + gw // 2, cy + gh // 2
    color = (int(rng.randint(150, 255)), int(rng.randint(40, 120)), int(rng.randint(40, 120)))
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness=rng.randint(10, 22))
    label = f"0 {cx / w:.6f} {cy / h:.6f} {gw / w:.6f} {gh / h:.6f}"
    return img, label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../test_images")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--labels", action="store_true",
                    help="Also write ground-truth YOLO labels (dataset_raw layout) "
                         "so train/export can be smoke-tested without the teacher model.")
    args = ap.parse_args()
    out = Path(args.out).expanduser()
    if args.labels:
        (out / "images").mkdir(parents=True, exist_ok=True)
        (out / "labels").mkdir(parents=True, exist_ok=True)
    else:
        out.mkdir(parents=True, exist_ok=True)
    for i in range(args.n):
        img, label = make_one(seed=i)
        if args.labels:
            cv2.imwrite(str(out / "images" / f"gate_{i:03d}.jpg"), img)
            (out / "labels" / f"gate_{i:03d}.txt").write_text(label)
        else:
            cv2.imwrite(str(out / f"gate_{i:03d}.jpg"), img)
    print(f"Wrote {args.n} synthetic gate images to {out.resolve()}"
          + (" (with labels)" if args.labels else ""))


if __name__ == "__main__":
    main()
