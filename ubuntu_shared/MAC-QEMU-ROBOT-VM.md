# Mac → UTM QEMU VM → PiPER robot

End-to-end guide for running the **AgileX PiPER** arm from a **Mac** using a **UTM QEMU** Ubuntu VM and the kit **candleLight** USB-CAN adapter (`1d50:606f`).

**Why QEMU:** Apple **Virtualize** VMs are fast but **cannot** pass USB to the guest. Robot CAN **requires** QEMU + USB sharing. See [USB-PASSTHROUGH.md](USB-PASSTHROUGH.md).

> **SDK note (`piper_sdk` vs `pyAgxArm`):** AgileX’s newer **[pyAgxArm](https://github.com/agilexrobotics/pyAgxArm)** driver is the intended successor to **`piper_sdk`** and is meant to support Mac natively (AgileX docs focus on **serial/SLCAN** CAN modules on macOS, not the kit **candleLight**). **This repo still uses `piper_sdk`** because our PiPER kit ships candleLight (`1d50:606f`), which works on **Linux SocketCAN** but not reliably on native Mac (`gs_usb` often blocked). The **QEMU VM below is a practical workaround** for this hardware — not AgileX’s long-term Mac-native path. A future migration to `pyAgxArm` may reduce or remove the need for a Linux VM.

**Split workflow (recommended):**

| Task | Where |
|------|--------|
| Vision, overlay, skeleton, MacBook/Piper camera tuning | **Mac** — `python main.py` / `vision.py` |
| CAN, `piper_sdk`, live arm | **QEMU Ubuntu VM** (this guide) |

---

## Prerequisites

- Mac with **Apple Silicon** (M-series)
- **UTM** installed ([getutm.app](https://getutm.app))
- **Ubuntu Server 24.04 or 26.04 ARM64** ISO
- PiPER kit: arm + **candleLight** CAN adapter
- Repo on Mac: `~/Projects/piper-vision-hackathon` (or your clone path)

**Do not rely on native Mac CAN** for candleLight — macOS often blocks `gs_usb` with `Errno 13`. Use the VM path below.

---

## Part 1 — Create the QEMU VM in UTM

### 1.1 New VM

1. UTM → **Create New Virtual Machine**
2. Choose **Emulate** (QEMU) — **not** “Virtualize” (Apple Virtualization)
3. **Linux** → **Ubuntu** (or Other Linux)
4. Architecture: **ARM64 (aarch64)**
5. RAM: **8 GB** (minimum 4 GB)
6. Disk: **64 GB** (or larger)
7. Save VM (example name: **`Linux`**)

### 1.2 Enable USB sharing

VM selected → **Settings** (gear):

- **QEMU** → **Input** (or Sharing) → enable **USB sharing**
- If USB attach fails later: try **disabling USB 3.0 (XHCI)** (use USB 2.0 cable/port)

### 1.3 Install Ubuntu Server

Boot from ISO. Suggested choices:

| Installer screen | Choice |
|------------------|--------|
| Archive mirror | **Default** / country mirror (ARM64 uses `ports.ubuntu.com` automatically) |
| Storage | **Use entire disk** — **no** manual LVM, **no** RAID |
| Layout | `/` ext4 + `/boot/efi` fat32 (installer default is fine) |
| OpenSSH | **Install OpenSSH server** — **yes** |
| SSH key | Paste Mac key: `cat ~/.ssh/id_ed25519.pub` — or skip and use `ssh-copy-id` later |
| Snaps | Optional — skip is fine |

When install finishes:

1. **Remove/eject** the ISO (UTM → Settings → Drives → clear CD/ISO)
2. Reboot into disk (not installer again)

### 1.4 First login

Note the VM IP (UTM shared network, often `192.168.64.x`):

```bash
hostname -I
# example: 192.168.64.4
```

Create user (example: **`philip`**) during install.

---

## Part 2 — SSH from Mac (not the UTM console)

Copy/paste works in **Mac Terminal** or **Cursor terminal**, not always in the UTM window.

### 2.1 macOS Local Network (Cursor only)

If SSH from **Cursor** fails with **“No route to host”** but Terminal.app works:

**System Settings → Privacy & Security → Local Network → enable Cursor**

### 2.2 Install SSH key (one time)

On the **Mac** (prompt `fio@MacBook...`, **not** inside `ssh philip@...`):

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub philip@192.168.64.4
```

Replace IP with your VM’s `hostname -I` result.

### 2.3 SSH config (optional)

`~/.ssh/config` on Mac:

```
Host ubuntu-robot-qemu
  HostName 192.168.64.4
  User philip
  IdentityFile ~/.ssh/id_ed25519
```

Test:

```bash
ssh ubuntu-robot-qemu 'echo OK'
```

---

## Part 3 — Software on the VM (no robot plugged in yet)

From **Mac**, sync project code:

```bash
ssh philip@192.168.64.4 'mkdir -p ~/piper-vision-hackathon/projects/lightsaber ~/piper-vision-hackathon/projects/shared'

rsync -az --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
  ~/Projects/piper-vision-hackathon/projects/lightsaber/ \
  philip@192.168.64.4:~/piper-vision-hackathon/projects/lightsaber/

rsync -az --exclude '__pycache__' \
  ~/Projects/piper-vision-hackathon/projects/shared/ \
  philip@192.168.64.4:~/piper-vision-hackathon/projects/shared/
```

On the **VM** (SSH session):

```bash
sudo apt update
sudo apt install -y git curl wget rsync python3 python3-venv python3-pip \
  can-utils usbutils net-tools libgl1 libglib2.0-0

curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"

cd ~/piper-vision-hackathon/projects/lightsaber
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
uv pip uninstall opencv-python opencv-contrib-python 2>/dev/null || true
uv pip install opencv-python-headless

source .venv/bin/activate
python -m unittest tests.test_contracts -q
python robot_smoke.py
```

Ubuntu **26.04** only ships Python 3.14 by default — **use uv + Python 3.12** as above (MediaPipe needs it).

---

## Part 4 — USB-CAN passthrough (robot plugged in)

Plug candleLight into the **Mac**. Attach it to the **VM**, not the Mac host.

### 4.1 UTM GUI

1. VM **running**, UTM window focused  
2. Toolbar → **USB** (plug icon)  
3. Select **candleLight USB to CAN adapter**

### 4.2 UTM CLI (reliable)

Optional symlink on Mac:

```bash
sudo ln -sf /Applications/UTM.app/Contents/MacOS/utmctl /usr/local/bin/utmctl
```

List VMs and USB devices:

```bash
utmctl list
utmctl usb list
```

Attach (replace VM name if yours differs). **Use full path if `utmctl` is not on PATH:**

```bash
/Applications/UTM.app/Contents/MacOS/utmctl usb connect "Linux" "1d50:606f"
# or after symlink: utmctl usb connect "Linux" "1d50:606f"
```

### 4.3 Verify on VM

```bash
lsusb | grep 1d50
# Bus ... ID 1d50:606f OpenMoko, Inc. Geschwister Schneider CAN adapter
```

If empty → USB not attached; repeat 4.1 or 4.2.

---

## Part 5 — Bring up CAN and discover the arm

On the **VM** (after USB attach from Part 4):

```bash
lsusb | grep 1d50
bash ~/piper-vision-hackathon/projects/ubuntu_shared/can-up.sh
# monorepo layout on VM — or use lightsaber/ubuntu_shared/can-up.sh if synced from git
# enter sudo password once per boot

timeout 3 candump can0
# expect many frames (0x2A1, 0x251–0x256, …). Empty = arm off or CAN cable unplugged.

cd ~/piper-vision-hackathon/projects/lightsaber
source .venv/bin/activate
python robot_discover.py
```

**Pass criteria:**

```
[OK] USB-CAN adapter
[OK] can0 — UP, bitrate 1000000
[OK] CAN frames
[OK] PiPER on bus — Hz=... joints(deg)=[...]
PASS — robot path looks good. Next: python robot_smoke.py --preflight
```

`piper_sdk` SyntaxWarnings are harmless.

**Keep code updated on VM** (rsync from Mac — the VM folder is often not a git clone):

```bash
rsync -az --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
  ~/Projects/piper-vision-hackathon/projects/lightsaber/ \
  philip@192.168.64.4:~/piper-vision-hackathon/projects/lightsaber/
```

---

## Part 6 — Robot smoke tests (milestone order)

All from VM, `source .venv/bin/activate`:

| Step | Command | What it proves |
|------|---------|----------------|
| Software only | `python robot_smoke.py` | DRY_RUN poses, no CAN |
| Preflight | `python robot_smoke.py --preflight` | Firmware, CAN send probe, read state (no motion) |
| Live connect | `python robot_smoke.py --connect` | Preflight, enable, hold **GUARD_CENTER** |
| Live motion | `python robot_smoke.py --live --pose HOME --i-know` | Test move → hold pose |
| Block pose | `python robot_smoke.py --live --pose BLOCK_LEFT --i-know` | After calibrating `poses.py` |

**Exit while holding:** **Enter** = close host CAN, **keep torque**. **Ctrl+C** = software e-stop (**DisableArm**, cuts torque).

Keep `DRY_RUN = True` in git. Speed: `ROBOT_MOVE_SPEED_PERCENT = 30` in `config.py`.

Full checklist: [VM-ROBOT-CHECKLIST.md](VM-ROBOT-CHECKLIST.md)

---

## Part 7 — Daily startup (after every Mac or VM reboot)

USB passthrough **does not persist**. Repeat **every session** — no reinstall.

**Mac** (VM must be running in UTM):

```bash
/Applications/UTM.app/Contents/MacOS/utmctl usb connect "Linux" "1d50:606f"
```

**VM:**

```bash
lsusb | grep 1d50
bash ~/piper-vision-hackathon/projects/ubuntu_shared/can-up.sh
timeout 3 candump can0
cd ~/piper-vision-hackathon/projects/lightsaber && source .venv/bin/activate
python robot_discover.py
python robot_smoke.py --preflight
```

| Symptom | Meaning |
|---------|---------|
| `can0` missing | Re-run `utmctl usb connect` on Mac |
| `can0` DOWN | Run `can-up.sh` |
| `candump` empty, `lsusb` OK | **Arm powered off** or CAN cable to arm unplugged |
| `candump` busy, discover FAIL | Rare — check bitrate 1000000, replug USB |

---

## Part 8 — Vision on Mac (parallel)

Robot on VM; camera/overlay on Mac until you pass the camera to the VM:

```bash
cd ~/Projects/piper-vision-hackathon/projects/lightsaber
source .venv/bin/activate
python vision.py --camera laptop
python main.py --camera piper   # Piper on Mac uses ffmpeg; see README
```

Piper camera on Mac: [../README.md](../README.md) § Camera.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `lsusb` no `1d50` on VM | QEMU VM + USB sharing; `utmctl usb connect ...` |
| candleLight on Mac, not VM | Attach via UTM USB; device leaves Mac when attached |
| `can0` missing | USB attached? `dmesg \| tail` (may need sudo) |
| `can0` DOWN | Run `can-up.sh` |
| `candump` empty but `lsusb` shows adapter | Arm **power off** or CAN cable to arm unplugged |
| SSH “No route to host” from Cursor | Local Network permission for Cursor |
| `ssh-copy-id` “No identities” on VM | Run **on Mac**, not inside VM SSH |
| Mac `robot_discover` Errno 13 | Expected for candleLight; use QEMU VM |
| `candump` not found | `sudo apt install can-utils` |
| Wrong Python / MediaPipe fail | Use **uv + Python 3.12** on Ubuntu 26 |

---

## Quick reference

| Item | Example value |
|------|----------------|
| VM backend | **QEMU** (Emulate) |
| VM name | `Linux` |
| VM IP | `192.168.64.4` (verify with `hostname -I`) |
| SSH user | `philip` |
| CAN adapter USB ID | `1d50:606f` |
| Interface | `can0` @ **1000000** bps |
| Code on VM | `~/piper-vision-hackathon/projects/lightsaber` |
| utmctl attach | `/Applications/UTM.app/Contents/MacOS/utmctl usb connect "Linux" "1d50:606f"` |

---

## Related docs

- [VM-ROBOT-CHECKLIST.md](VM-ROBOT-CHECKLIST.md) — robot milestones
- [USB-PASSTHROUGH.md](USB-PASSTHROUGH.md) — why Virtualize fails
- [ENVIRONMENT.md](ENVIRONMENT.md) — hardware summary
- [../MAC-ROBOT.md](../MAC-ROBOT.md) — Mac-native CAN (limited)
- [../PLATFORM.md](../PLATFORM.md) — Mac vs Linux roles
- [CURSOR-REMOTE-SSH.md](CURSOR-REMOTE-SSH.md) — edit VM code from Cursor
