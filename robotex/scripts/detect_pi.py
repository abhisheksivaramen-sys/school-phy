#!/usr/bin/env python3
"""
Step 5 — Gate detection on the Raspberry Pi 4B + CH8 autonomous handover.

On-drone script. Two ways to run it:

A) Detection only (no motors) — always do this first:
       python detect_pi.py --model best_ncnn_model --show

B) CH8 autonomous handover on the real aircraft (PROPS OFF for first tests):
       python detect_pi.py --model best_ncnn_model \
           --mavlink /dev/serial0 --baud 921600 --fly --ch8-handover

How the CH8 handover works
--------------------------
* You fly/arm normally. Your Skydroid CH8 switch is watched by THIS script.
* Flip CH8 HIGH  -> the Pi takes over: sets GUIDED, arms (if needed), climbs to
  --takeoff-alt, then steers through gates with the vision guidance.
* Flip CH8 LOW   -> the Pi lets go: commands LOITER (position-hold on optical
  flow) and stops sending guidance, so you fly manually again.
* You can ALWAYS override instantly by moving your own flight-mode switch out of
  GUIDED on the transmitter — ArduPilot hands control straight back to you.

SAFETY: --fly + --ch8-handover arm and move a real aircraft. Test with props
removed, then in a large netted/open area, hand on the transmitter at all times.
Optical flow must be healthy (textured, well-lit floor) or GUIDED position
control will drift. You are responsible for safe operation.
"""
import argparse
import time

import cv2

# ArduCopter flight-mode numbers (custom_mode) used with DO_SET_MODE.
COPTER_MODES = {"STABILIZE": 0, "ALT_HOLD": 2, "AUTO": 3, "GUIDED": 4,
                "LOITER": 5, "RTL": 6, "LAND": 9}


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
                   help="Serial port or UDP to Pixhawk, e.g. /dev/serial0 or udp:127.0.0.1:14550")
    p.add_argument("--baud", type=int, default=921600, help="Serial baud for Pixhawk link.")
    p.add_argument("--fly", action="store_true",
                   help="ACTUALLY send commands. Off = compute only, no motion (safe dry run).")
    p.add_argument("--fwd-speed", type=float, default=0.6, help="Forward m/s when gate is centred.")
    p.add_argument("--max-yaw", type=float, default=0.5, help="Max yaw rate (rad/s).")
    p.add_argument("--kp-yaw", type=float, default=1.2, help="P-gain: horizontal error -> yaw.")
    p.add_argument("--kp-vz", type=float, default=0.4, help="P-gain: vertical error -> climb/descend.")

    # --- CH8 autonomous handover ---
    p.add_argument("--ch8-handover", action="store_true",
                   help="Watch CH8: HIGH = Pi takes over (GUIDED+arm+takeoff+guide), LOW = LOITER.")
    p.add_argument("--ch8-chan", type=int, default=8, help="RC channel to watch for handover.")
    p.add_argument("--ch8-high", type=int, default=1700, help="PWM above this = engage autonomy.")
    p.add_argument("--takeoff-alt", type=float, default=1.2, help="Guided takeoff height (m).")
    return p.parse_args()


class PixhawkLink:
    """MAVLink helper: velocity setpoints, mode changes, arming, takeoff, RC read."""

    def __init__(self, conn_str, baud):
        from pymavlink import mavutil
        self.mavutil = mavutil
        self.mav = mavutil.mavlink
        print(f"Connecting to Pixhawk on {conn_str} ...")
        self.m = mavutil.mavlink_connection(conn_str, baud=baud)
        self.m.wait_heartbeat()
        self.sys, self.comp = self.m.target_system, self.m.target_component
        print(f"  heartbeat from system {self.sys} component {self.comp}")

    # ---- telemetry ----
    def read_channel(self, chan):
        """Latest PWM (us) for an RC input channel, or None if not seen yet."""
        msg = self.m.recv_match(type="RC_CHANNELS", blocking=False)
        if msg is None:
            return getattr(self, "_last_rc", None) and self._last_rc.get(chan)
        rc = {i: getattr(msg, f"chan{i}_raw", 0) for i in range(1, 17)}
        self._last_rc = rc
        return rc.get(chan)

    def is_armed(self):
        hb = self.m.recv_match(type="HEARTBEAT", blocking=False)
        if hb is not None:
            self._armed = bool(hb.base_mode & self.mav.MAV_MODE_FLAG_SAFETY_ARMED)
        return getattr(self, "_armed", False)

    # ---- commands ----
    def set_mode(self, name):
        num = COPTER_MODES[name]
        self.m.mav.command_long_send(
            self.sys, self.comp, self.mav.MAV_CMD_DO_SET_MODE, 0,
            self.mav.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, num, 0, 0, 0, 0, 0)

    def arm(self, arm=True):
        self.m.mav.command_long_send(
            self.sys, self.comp, self.mav.MAV_CMD_COMPONENT_ARM_DISARM, 0,
            1 if arm else 0, 0, 0, 0, 0, 0, 0)

    def takeoff(self, alt):
        self.m.mav.command_long_send(
            self.sys, self.comp, self.mav.MAV_CMD_NAV_TAKEOFF, 0,
            0, 0, 0, 0, 0, 0, alt)

    def send_velocity(self, vx, vy, vz, yaw_rate):
        """vx fwd, vy right, vz down (m/s), yaw_rate rad/s — MAV_FRAME_BODY_NED."""
        mask = 0b0000011111000111  # use velocity + yaw_rate only
        self.m.mav.set_position_target_local_ned_send(
            0, self.sys, self.comp, self.mav.MAV_FRAME_BODY_NED, mask,
            0, 0, 0, vx, vy, vz, 0, 0, 0, 0, yaw_rate)

    def hold(self):
        self.send_velocity(0, 0, 0, 0)


def largest_gate(result):
    """Return (cx, cy, area) of the biggest detected gate box, or None."""
    best, best_area = None, 0.0
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        area = (x2 - x1) * (y2 - y1)
        if area > best_area:
            best_area, best = area, ((x1 + x2) / 2, (y1 + y2) / 2, area)
    return best


def guidance_from_gate(gate, w, h, args):
    """Map a gate position to (vx, vy, vz, yaw, status)."""
    if not gate:
        return 0.0, 0.0, 0.0, 0.0, "no gate — holding"
    gx, gy, _ = gate
    ex = (gx - w / 2) / (w / 2)   # + => gate right of centre
    ey = (gy - h / 2) / (h / 2)   # + => gate below centre
    yaw = max(-args.max_yaw, min(args.max_yaw, args.kp_yaw * ex))
    vz = args.kp_vz * ey          # +vz descends (NED down positive)
    vx = args.fwd_speed if abs(ex) < 0.25 else 0.0  # go forward only when lined up
    return vx, 0.0, vz, yaw, f"gate ex={ex:+.2f} ey={ey:+.2f} vx={vx:.2f} yaw={yaw:+.2f}"


def main():
    args = parse_args()
    from ultralytics import YOLO

    model = YOLO(args.model, task="detect")
    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open camera/source: {args.source}")

    link = None
    if args.mavlink:
        link = PixhawkLink(args.mavlink, args.baud)
        if args.fly:
            print("MAVLink control ARMED (--fly). Keep the transmitter ready.")
        else:
            print("MAVLink connected but --fly not set: computing only, NOT sending.")
        if args.ch8_handover:
            print(f"CH8 handover on: ch{args.ch8_chan} > {args.ch8_high} engages autonomy.")

    engaged = False           # is the Pi currently flying?
    t_prev, fps = time.time(), 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            h, w = frame.shape[:2]
            res = model.predict(frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
            gate = largest_gate(res)
            vx, vy, vz, yaw, gstatus = guidance_from_gate(gate, w, h, args)

            mode_status = ""
            if link and args.ch8_handover:
                pwm = link.read_channel(args.ch8_chan)
                want = pwm is not None and pwm > args.ch8_high
                if want and not engaged:               # rising edge: take over
                    engaged = True
                    mode_status = "CH8 HIGH -> GUIDED + arm + takeoff"
                    if args.fly:
                        link.set_mode("GUIDED")
                        if not link.is_armed():
                            link.arm(True)
                        link.takeoff(args.takeoff_alt)
                elif not want and engaged:             # falling edge: hand back
                    engaged = False
                    mode_status = "CH8 LOW -> LOITER (manual)"
                    if args.fly:
                        link.set_mode("LOITER")
                else:
                    mode_status = f"ch{args.ch8_chan}={pwm} engaged={engaged}"

                if engaged and args.fly:
                    link.send_velocity(vx, vy, vz, yaw)
            elif link and args.fly:
                link.send_velocity(vx, vy, vz, yaw)     # no handover: always guide

            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(1e-6, now - t_prev))
            t_prev = now
            print(f"\r{fps:4.1f}FPS | {gstatus} | {mode_status}        ", end="", flush=True)

            if args.show:
                cv2.imshow("gate", res.plot())
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        if link and args.fly:
            link.hold()             # stop motion
            if args.ch8_handover:
                link.set_mode("LOITER")  # leave it hovering, not commanding forward
        cap.release()
        cv2.destroyAllWindows()
        print("\nStopped.")


if __name__ == "__main__":
    main()
