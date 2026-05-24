# VM robot control checklist

**Deferred:** live vision overlay (skeleton) — see [task-vision.md](../task-vision.md) on Mac, or VM desktop later.

## Prerequisites (you)

- [ ] UTM VM running, SSH: `ssh ubuntu-robot`
- [ ] USB **CAN adapter** passed to VM — **QEMU backend only** ([USB-PASSTHROUGH.md](USB-PASSTHROUGH.md)); Apple Virtualization cannot see host USB
- [ ] On VM: `bash ~/piper-vision-hackathon/projects/lightsaber/ubuntu_shared/can-up.sh` (sudo once per boot)
- [ ] Arm powered, clear workspace, people clear

## Automated / agent (from Mac)

```bash
# Sync code
rsync -az --exclude '.venv' --exclude '__pycache__' \
  projects/lightsaber/ ubuntu-robot:~/piper-vision-hackathon/projects/lightsaber/

# On VM via SSH
ssh ubuntu-robot 'cd ~/piper-vision-hackathon/projects/lightsaber && source .venv/bin/activate && python robot_smoke.py'
ssh ubuntu-robot 'cd ~/piper-vision-hackathon/projects/lightsaber && source .venv/bin/activate && python robot_discover.py'
```

## Milestones

| Step | Command | Pass criteria |
|------|---------|----------------|
| **1** | **`python robot_discover.py`** | USB-CAN seen, `can0` UP, CAN frames, PiPER joint feedback |
| 2 | `python robot_smoke.py` | DRY_RUN prints HOME / BLOCK_* (software only) |
| 2b | `python robot_smoke.py --preflight` | Firmware, CAN probe send, joint/status read (no motion) |
| 3 | `python robot_smoke.py --connect` | Preflight, then LIVE enable + HOME |
| 4 | `python robot_smoke.py --live --pose HOME --i-know` | Arm moves to HOME slowly |
| 5 | Calibrate `poses.py`, then test BLOCK_LEFT | Safe, small motion |

`config.py`: keep `DRY_RUN = True` in git; use `--live` only for controlled tests.

## Overlay (later)

- Mac: `python main.py --camera piper` with `SHOW_PREVIEW = True`
- VM: minimal desktop + `opencv-python` (not headless) when camera is on VM
