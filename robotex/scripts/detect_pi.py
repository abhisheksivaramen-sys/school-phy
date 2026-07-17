#!/usr/bin/env python3
"""
Step 5 — Run gate detection on the Raspberry Pi 4B (the companion computer),
and (optionally) steer the drone toward the gate via MAVLink to the Pixhawk.

This is the on-drone script. It:
  1. Grabs frames from the camera.
  2. Detects the gate with your exported NCNN model.
  3. Computes how far the gate is left/right/up/down from image centre.
  4. (optional --mavlink) sends body-frame velocity commands to the Pixhawk so
     the drone yaws/strafes to line up with the gate and moves forward through it.

Run detection only (no motors) first, to verify the model works on the Pi:
    python detect_pi.py --model best_ncnn_model --show

Then, on the real aircraft (props off first!), enable guidance:
    python detect_pi.py --model best_ncnn_model \
        --mavlink /dev/ttyAMA0 --baud 921600 --fly

SAFETY: --fly sends movement commands. Test on the bench with props removed,
in a large open area, with a human on the Skydroid T10 ready to flip back to
MANUAL/STABILIZE at any instant. You are responsible for safe operation.
"""
import argparse
import time

import cv2


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True,
                   help="Path to best_ncnn_model folder (or best.onnx / best.pt).")
    p.add_argument("--source", default="0",
                   help="Camera index (0) or a video file path for testing.")
    p.add_argument("--imgsz", type=int, default=416,
                   help="Inference size. Must match what you exported. Lower = faster.")
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--show", action="store_true", help="Show a preview window (needs a display).")

    # --- MAVLink / flight options (all optional) ---
    p.add_argument("--mavlink", default=None,
                   help="Serial port or UDP to Pixhawk, e.g. /dev/ttyAMA0 or udp:127.0.0.1:14550")
    p.add_argument("--baud", type=int, default=921600, help="Serial baud for Pixhawk link.")
    p.add_argument("--fly", action="store_true",
                   help="ACTUALLY send velocity commands. Off = compute only, no motion.")
    p.add_argument("--fwd-speed", type=float, default=0.6, help="Forward m/s when gate is centred.")
    p.add_argument("--max-yaw", type=float, default=0.5, help="Max yaw rate (rad/s).")
    p.add_argument("--kp-yaw", type=float, default=1.2, help="P-gain: horizontal error -> yaw.")
    p.add_argument("--kp-vz", type=float, default=0.4, help="P-gain: vertical error -> climb/descend.")
    return p.parse_args()


class PixhawkLink:
    """Thin MAVLink wrapper for sending body-frame velocity + yaw-rate setpoints."""

    def __init__(self, conn_str, baud):
        from pymavlink import mavutil
        self.mavutil = mavutil
        print(f"Connecting to Pixhawk on {conn_str} ...")
        self.m = mavutil.mavlink_connection(conn_str, baud=baud)
        self.m.wait_heartbeat()
        print(f"  heartbeat from system {self.m.target_system} component {self.m.target_component}")

    def send_velocity(self, vx, vy, vz, yaw_rate):
        """vx fwd, vy right, vz down (m/s), yaw_rate rad/s — MAV_FRAME_BODY_NED."""
        mav = self.mavutil.mavlink
        # type_mask: ignore position & accel, use velocity + yaw_rate
        mask = 0b0000011111000111
        self.m.mav.set_position_target_local_ned_send(
            0, self.m.target_system, self.m.target_component,
            mav.MAV_FRAME_BODY_NED, mask,
            0, 0, 0,            # x,y,z position (ignored)
            vx, vy, vz,         # velocity
            0, 0, 0,            # accel (ignored)
            0, yaw_rate)        # yaw (ignored), yaw_rate

    def hold(self):
        self.send_velocity(0, 0, 0, 0)


def largest_gate(result):
    """Return (cx, cy, area_frac) of the biggest gate box, or None."""
    best, best_area = None, 0.0
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        area = (x2 - x1) * (y2 - y1)
        if area > best_area:
            best_area = area
            best = ((x1 + x2) / 2, (y1 + y2) / 2, area)
    return best


def main():
    args = parse_args()
    from ultralytics import YOLO

    model = YOLO(args.model, task="detect")
    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open camera/source: {args.source}")

    link = None
    if args.mavlink and args.fly:
        link = PixhawkLink(args.mavlink, args.baud)
        print("MAVLink guidance ARMED (--fly). Keep the RC transmitter ready.")
    elif args.mavlink:
        print("MAVLink port given but --fly not set: computing commands only, NOT sending.")

    t_prev, fps = time.time(), 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            h, w = frame.shape[:2]
            res = model.predict(frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
            gate = largest_gate(res)

            vx = vy = vz = yaw = 0.0
            if gate:
                gx, gy, area = gate
                # normalised error from image centre, range roughly [-1, 1]
                ex = (gx - w / 2) / (w / 2)     # + => gate is to the right
                ey = (gy - h / 2) / (h / 2)     # + => gate is below centre
                yaw = max(-args.max_yaw, min(args.max_yaw, args.kp_yaw * ex))
                vz = args.kp_vz * ey            # +vz = descend (NED down is +)
                # only push forward once we're roughly lined up
                vx = args.fwd_speed if abs(ex) < 0.25 else 0.0
                status = f"gate ex={ex:+.2f} ey={ey:+.2f} -> vx={vx:.2f} yaw={yaw:+.2f}"
            else:
                status = "no gate — holding"

            if link:
                link.send_velocity(vx, vy, vz, yaw)

            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(1e-6, now - t_prev))
            t_prev = now
            print(f"\r{fps:4.1f} FPS | {status}        ", end="", flush=True)

            if args.show:
                cv2.imshow("gate", res.plot())
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        if link:
            link.hold()  # stop the aircraft on exit
        cap.release()
        cv2.destroyAllWindows()
        print("\nStopped.")


if __name__ == "__main__":
    main()
