# Connecting to your Raspberry Pi 4B (it's in another state) via Tailscale

Your Pi is far away on some other Wi-Fi network. That's fine — **Tailscale gives
every device a private IP that works from anywhere**, as long as both the Pi and
the machine you're on are signed into the *same Tailscale account (tailnet)* and
both have internet. You never need to know or touch the remote Wi-Fi.

> Important: **I (this cloud session) cannot join your tailnet or reach the Pi.**
> You connect from **your own laptop**. Do the steps below on your laptop.

---

## One-time setup

### On the Pi (you said Tailscale is already installed — just confirm it's up)
If you can get to the Pi even once (locally, or it's already reachable):
```bash
sudo tailscale up            # opens a login link; sign in to your account
tailscale ip -4              # prints the Pi's tailnet IP, e.g. 100.101.102.103
tailscale status             # should say the Pi is "active"
```
Make it reconnect automatically after reboot/power-loss (so you don't need
physical access again):
```bash
sudo tailscale up --ssh                       # optional: enables Tailscale SSH
sudo systemctl enable --now tailscaled        # start on boot
```
`--ssh` lets you SSH over Tailscale without managing keys — handy when the Pi is
in another state.

### On your laptop
1. Install Tailscale (https://tailscale.com/download) and sign in to the **same account**.
2. Check the Pi shows up:
   ```bash
   tailscale status         # you should see the Pi and its 100.x.y.z IP
   ```

---

## Every time you want in

```bash
# find the Pi's tailnet IP (or a name like 'raspberrypi')
tailscale status

# SSH in using that IP
ssh pi@100.101.102.103
# or, with MagicDNS enabled, just:
ssh pi@raspberrypi
```

### Copy your trained model to the Pi (over Tailscale)
From your laptop, after training finishes:
```bash
scp -r robotex/scripts/runs/detect/gate_yolov8n/weights/best_ncnn_model \
       pi@100.101.102.103:~/robotex/
scp robotex/scripts/detect_pi.py  pi@100.101.102.103:~/robotex/
```

Then on the Pi:
```bash
ssh pi@100.101.102.103
cd ~/robotex
pip install ultralytics opencv-python pymavlink
python detect_pi.py --model best_ncnn_model --imgsz 416 --show
```

---

## The catch you must plan for

Tailscale only reaches the Pi **while the Pi is powered on and has internet** in
that other state. If it's currently off or unplugged, someone physically there
has to power it and make sure it joins its Wi-Fi. Once it's on and on the tailnet,
you can reach it from anywhere, indefinitely.

**Recommendation:** since the Pi is in another state, do all the **training on
your laptop** (fast, no Pi needed). Only touch the Pi at the very end to copy the
model and run `detect_pi.py`. That way a flaky remote Pi never blocks your work.

## Troubleshooting
- `ssh: connect ... timed out` → the Pi isn't online on the tailnet. Check
  `tailscale status`; the Pi must be powered and have internet.
- Pi IP keeps changing? It doesn't — tailnet IPs are stable. Use MagicDNS names
  (Settings → enable MagicDNS) so you can `ssh pi@raspberrypi`.
- Can SSH but no camera in `detect_pi.py`? Enable the camera (`sudo raspi-config`
  → Interface → Camera) and check `--source 0` vs the correct index.
