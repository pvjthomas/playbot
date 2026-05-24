# VM robot control checklist

**Deferred:** live vision overlay (skeleton) — see [task-vision.md](../task-vision.md) on Mac, or VM desktop later.

Full setup guide: **[MAC-QEMU-ROBOT-VM.md](MAC-QEMU-ROBOT-VM.md)**

---

## Daily startup (every Mac or VM reboot)

USB attach **does not persist**. Run this **every session** before robot commands.

**1. Mac** — VM running in UTM, candleLight plugged into Mac:

```bash
/Applications/UTM.app/Contents/MacOS/utmctl usb connect "Linux" "1d50:606f"
```

(Symlink optional: `sudo ln -sf /Applications/UTM.app/Contents/MacOS/utmctl /usr/local/bin/utmctl`)

**2. VM** — SSH in (`ssh philip@192.168.64.4` or your IP):

```bash
lsusb | grep 1d50                    # must show candleLight
bash ~/piper-vision-hackathon/projects/ubuntu_shared/can-up.sh   # sudo once per boot
# or: bash ~/piper-vision-hackathon/projects/lightsaber/ubuntu_shared/can-up.sh

timeout 3 candump can0               # should flood with frames (not empty!)
cd ~/piper-vision-hackathon/projects/lightsaber && source .venv/bin/activate
python robot_discover.py             # must PASS
```

**If `candump` is empty** but `lsusb` shows `1d50:606f`: adapter is OK — **power on PiPER** and check **CAN cable** to the arm.

**3. Sync code from Mac** (VM is usually rsync, not git):

```bash
# on Mac
rsync -az --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
  ~/Projects/piper-vision-hackathon/projects/lightsaber/ \
  philip@192.168.64.4:~/piper-vision-hackathon/projects/lightsaber/
```

---

## Prerequisites (you)

- [ ] UTM **QEMU** VM running (not Apple Virtualization) — [USB-PASSTHROUGH.md](USB-PASSTHROUGH.md)
- [ ] SSH to VM (example: `philip@192.168.64.4`)
- [ ] Daily startup above completed
- [ ] Arm powered, clear workspace, people clear

## Milestones

| Step | Command | Pass criteria |
|------|---------|----------------|
| **1** | **`python robot_discover.py`** | USB-CAN, `can0` UP, CAN frames, PiPER joint feedback |
| 2 | `python robot_smoke.py` | DRY_RUN prints HOME / BLOCK_* (software only) |
| **2b** | **`python robot_smoke.py --preflight`** | Firmware, CAN probe send, joint/status (no motion) |
| 3 | `python robot_smoke.py --connect` | Preflight + LIVE enable; hold **GUARD_CENTER** |
| 4 | `python robot_smoke.py --live --pose HOME --i-know` | Test move → hold; **Enter** or **Ctrl+C** to exit |

**While holding:** **Enter** closes host CAN (arm keeps torque). **Ctrl+C** = software e-stop (DisableArm).
| 5 | Calibrate `poses.py`, then `BLOCK_LEFT` | After teaching real block angles |
| 6 | Vision on Mac + robot on VM | `main.py` with `DRY_RUN=True` first |

`config.py`: keep `DRY_RUN = True` in git; use `--live` only for controlled tests. Speed: `ROBOT_MOVE_SPEED_PERCENT = 30`.

## What to run next (after discover PASS)

You are here if `robot_discover.py` and `candump` show traffic:

```bash
cd ~/piper-vision-hackathon/projects/lightsaber && source .venv/bin/activate
python robot_smoke.py --preflight          # firmware + state, no motion
python robot_smoke.py --connect              # enable + hold GUARD_CENTER
python robot_smoke.py --live --pose HOME --i-know

# While holding: Enter = exit keeping torque | Ctrl+C = software e-stop (cuts torque)
```

Then on **Mac** (vision, parallel):

```bash
cd ~/Projects/piper-vision-hackathon/projects/lightsaber && source .venv/bin/activate
python vision.py --camera laptop
# later: python main.py  (DRY_RUN=True until poses calibrated)
```

Do **not** use `BLOCK_*` poses until you calibrate angles in `poses.py` on hardware.

## Overlay (later)

- Mac: `python main.py --camera piper` with `SHOW_PREVIEW = True`
- VM: minimal desktop + `opencv-python` (not headless) when camera is on VM
