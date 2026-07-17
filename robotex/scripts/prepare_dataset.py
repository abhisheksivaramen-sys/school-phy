#!/usr/bin/env python3
"""
Step 2 — Split the auto-labelled data into train/val and wire up the config.

Takes the flat `dataset_raw/{images,labels}` produced by auto_label.py and
produces the train/val folder layout Ultralytics expects, then points
config/gate.yaml at it.

Usage
-----
    python prepare_dataset.py --raw ../dataset_raw --out ../dataset --val-split 0.2
"""
import argparse
import random
import shutil
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--raw", default="../dataset_raw",
                   help="Folder from auto_label.py (has images/ and labels/).")
    p.add_argument("--out", default="../dataset", help="Where to build train/val.")
    p.add_argument("--val-split", type=float, default=0.2,
                   help="Fraction of images used for validation (0.2 = 20%%).")
    p.add_argument("--seed", type=int, default=42, help="Deterministic shuffle seed.")
    p.add_argument("--config", default="../config/gate.yaml",
                   help="gate.yaml to update with the absolute dataset path.")
    return p.parse_args()


def main():
    args = parse_args()
    raw = Path(args.raw).expanduser()
    out = Path(args.out).expanduser()
    img_src, lbl_src = raw / "images", raw / "labels"
    if not img_src.is_dir():
        raise SystemExit(f"Not found: {img_src} (run auto_label.py first)")

    imgs = sorted(f for f in img_src.iterdir() if f.suffix.lower() in IMG_EXTS)
    if not imgs:
        raise SystemExit(f"No images in {img_src}")

    random.seed(args.seed)
    random.shuffle(imgs)
    n_val = max(1, int(len(imgs) * args.val_split))
    val_set = set(imgs[:n_val])

    for split in ("train", "val"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    counts = {"train": 0, "val": 0}
    for img in imgs:
        split = "val" if img in val_set else "train"
        lbl = lbl_src / f"{img.stem}.txt"
        shutil.copy2(img, out / "images" / split / img.name)
        if lbl.exists():
            shutil.copy2(lbl, out / "labels" / split / lbl.name)
        else:
            # no label file => empty (background) image; write an empty label
            (out / "labels" / split / f"{img.stem}.txt").write_text("")
        counts[split] += 1

    # point gate.yaml at the absolute dataset path so training works from anywhere
    cfg_path = Path(args.config).expanduser()
    if cfg_path.exists():
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text())
        cfg["path"] = str(out.resolve())
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
        print(f"Updated {cfg_path} -> path: {out.resolve()}")

    print(f"\nDataset ready at {out.resolve()}")
    print(f"  train images: {counts['train']}")
    print(f"  val   images: {counts['val']}")
    print("\nNext: python train.py")


if __name__ == "__main__":
    main()
