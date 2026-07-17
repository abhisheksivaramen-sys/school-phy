#!/usr/bin/env python3
"""
DJI Tello — autonomous flight through gates.

Runs entirely on your LAPTOP (connect the laptop's WiFi to the Tello's TELLO-XXXX
network first). No Raspberry Pi, no Pixhawk, no Mission Planner needed.

Pipeline: Tello video stream -> YOLO gate detection -> flight commands that yaw/
strafe to centre each gate, drive forward through it, then look for the next one.

Install (laptop):
    pip install djitellopy ultralytics opencv-python

Detection model — two choices:
  A) Your trained nano (fast, accurate, needs training first):
        python tello_gate_run.py --model ../runs/detect/gate_yolov8n/weights/best.pt
  B) No training — open-vocabulary teacher finds "gate" directly (needs a decent
     laptop/GPU; slower on CPU):
        python tello_gate_run.py --world --prompt "gate"

FIRST RUN — do this on the ground, props spinning disabled by NOT taking off:
        python tello_gate_run.py --model best.pt --no-fly
    This shows the video with gate boxes and prints the commands it WOULD send,
    but never takes off. Confirm it sees the gates before you let it fly.

CONTROLS (focus the video window):
    t = takeoff      l = land       q = land + quit
    SPACE = EMERGENCY stop motors (drops out of the sky — last resort)
    s = toggle autonomous steering on/off (manual hover when off)

SAFETY: fly in a clear/netted area, keep the video window focused so keys work,
and keep a hand ready to hit 'l' or SPACE. Start with low --speed. You are
responsible for safe operation.
"""
import argparse
import time

import cv2
import numpy as np


def parse_args():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--model", help="Path to trained YOLO gate model (best.pt / .onnx / ncnn).")
    g.add_argument("--world", action="store_true",
                   help="Use open-vocabulary YOLO-World instead of a trained model.")
    p.add_argument("--prompt", default="gate", help="Text prompt when using --world.")
    p.add_argument("--world-model", default="yolov8s-worldv2.pt",
                   help="Which YOLO-World weights (…s… faster, …x… more accurate).")
    p.add_argument("--imgsz", type=int, default=416)
    p.add_argument("--conf", type=float, default=0.35)

    p.add_argument("--no-fly", action="store_true",
                   help="Never take off. Show detections + print intended commands only.")
    p.add_argument("--speed", type=int, default=25,
                   help="Base forward speed 0-100 (start LOW, e.g. 20-30).")
    p.add_argument("--kp-yaw", type=float, default=60.0, help="Gain: horizontal error -> yaw.")
    p.add_argument("--kp-ud", type=float, default=50.0, help="Gain: vertical error -> up/down.")
    p.add_argument("--kp-lr", type=float, default=25.0, help="Gain: horizontal error -> strafe.")
    p.add_argument("--pass-area", type=float, default=0.22,
                   help="When the gate box covers this fraction of the frame, punch through.")
    p.add_argument("--pass-frames", type=int, default=18,
                   help="Frames to drive straight forward while passing through a gate.")
    p.add_argument("--search-yaw", type=int, default=25,
                   help="Yaw speed used to hunt for a gate when none is visible.")
    p.add_argument("--max-gates", type=int, default=0,
                   help="Land after this many gates (0 = keep going until you land it).")
    p.add_argument("--min-battery", type=int, default=15,
                   help="Refuse takeoff / auto-land below this battery %.")
    return p.parse_args()


def clamp(v, lo=-100, hi=100):
    return int(max(lo, min(hi, v)))


def largest_gate(result):
    """Return (cx, cy, area_frac) of the biggest gate box in normalised coords, or None."""
    best, best_area = None, 0.0
    h, w = result.orig_shape
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        area = (x2 - x1) * (y2 - y1)
        if area > best_area:
            best_area = area
            best = ((x1 + x2) / 2 / w, (y1 + y2) / 2 / h, area / (w * h))
    return best


def load_model(args):
    from ultralytics import YOLO
    if args.world:
        m = YOLO(args.world_model)
        m.set_classes([c.strip() for c in args.prompt.split(",") if c.strip()])
        return m
    return YOLO(args.model, task="detect")


def main():
    args = parse_args()
    from djitellopy import Tello

    model = load_model(args)

    tello = Tello()
    tello.connect()
    batt = tello.get_battery()
    print(f"Tello connected. Battery {batt}%.")
    if batt < args.min_battery:
        print(f"Battery below {args.min_battery}% — charge before flying.")
    tello.streamon()
    frame_read = tello.get_frame_read()

    flying = False
    steering = True
    passing = 0            # >0 => currently punching through a gate (frames left)
    gates_done = 0
    lost = 0               # frames since we last saw a gate

    print("Window keys: t=takeoff l=land q=quit SPACE=EMERGENCY s=toggle-steer")
    try:
        while True:
            frame = frame_read.frame
            if frame is None:
                continue
            # djitellopy returns RGB; convert for correct colours + model input.
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            h, w = frame.shape[:2]

            res = model.predict(frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
            gate = largest_gate(res)

            lr = fb = ud = yaw = 0
            if passing > 0:
                fb = args.speed          # blind forward punch through the gate
                passing -= 1
                status = f"PASS ({passing})"
                if passing == 0:
                    gates_done += 1
                    print(f"\n>>> gate {gates_done} cleared")
            elif gate:
                lost = 0
                ex = (gate[0] - 0.5) * 2   # -1..1, + => gate is right
                ey = (gate[1] - 0.5) * 2   # -1..1, + => gate is low
                yaw = clamp(args.kp_yaw * ex)
                lr = clamp(args.kp_lr * ex)
                ud = clamp(-args.kp_ud * ey)
                fb = args.speed if abs(ex) < 0.30 else 0   # forward only when lined up
                status = f"TRACK ex={ex:+.2f} ey={ey:+.2f} area={gate[2]:.2f}"
                if gate[2] >= args.pass_area:              # close enough -> go through
                    passing = args.pass_frames
                    status = "-> PASS"
            else:
                lost += 1
                yaw = args.search_yaw if lost > 5 else 0    # hunt for a gate
                status = "SEARCH" if lost > 5 else "no gate"

            # send commands (or just report in --no-fly / not flying / steering off)
            if flying and steering and not args.no_fly:
                tello.send_rc_control(lr, fb, ud, yaw)
            elif flying and not steering:
                tello.send_rc_control(0, 0, 0, 0)          # manual hover

            if args.max_gates and gates_done >= args.max_gates:
                print("\nAll gates done — landing.")
                break
            if flying and tello.get_battery() < args.min_battery:
                print("\nLow battery — landing.")
                break

            # HUD
            disp = res.plot()
            cv2.putText(disp, f"{status} | fly={flying} steer={steering} gates={gates_done}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Tello gate run", disp)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("t") and not flying and not args.no_fly:
                if tello.get_battery() >= args.min_battery:
                    tello.takeoff(); flying = True; print("\nTAKEOFF")
                else:
                    print("\nBattery too low to take off.")
            elif key == ord("l"):
                if flying:
                    tello.land(); flying = False; print("\nLAND")
            elif key == ord("s"):
                steering = not steering; print(f"\nsteering={steering}")
            elif key == ord(" "):
                tello.emergency(); flying = False; print("\nEMERGENCY STOP")
            elif key == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if flying:
                tello.land()
        except Exception:
            pass
        try:
            tello.streamoff()
        except Exception:
            pass
        cv2.destroyAllWindows()
        print("\nStopped.")


if __name__ == "__main__":
    main()
