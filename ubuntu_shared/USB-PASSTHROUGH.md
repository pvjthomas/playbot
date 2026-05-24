# USB-CAN passthrough (Mac → UTM Ubuntu)

Your **candleLight** adapter (`1d50:606f`) shows on the **Mac** but not in the VM because this VM uses **Apple Virtualization** — UTM **cannot** pass through host USB on that backend.

> **SDK context:** AgileX’s **`pyAgxArm`** is the newer driver with intended **Mac-native** support; this repo uses **`piper_sdk`** + **candleLight**, which needs **Linux SocketCAN** (QEMU VM USB passthrough below).

Official docs: [UTM USB sharing](https://docs.getutm.app/guest-support/sharing/usb/) — **QEMU backend only**.

---

## Confirm the problem

**Mac** (should see candleLight):

```bash
system_profiler SPUSBDataType | grep -A6 -i candle
```

**VM** (today you only see Apple virtual devices):

```bash
ssh ubuntu-robot lsusb
# Expect 1d50:606f after fix — not just 05ac:8105 keyboard, 05ac:1503 storage
```

```bash
ssh ubuntu-robot 'cd ~/piper-vision-hackathon/projects/lightsaber && source .venv/bin/activate && python robot_discover.py'
```

---

## Fix options

### Option A — New QEMU VM for robot (recommended)

Keep your current VM for SSH/dev; add a **second** Ubuntu VM (or replace) with:

1. UTM → **Create New Virtual Machine**
2. Choose **Emulate** / **QEMU** (not “Virtualize” / Apple Virtualization)
3. Ubuntu 24.04/26.04 **ARM64**
4. VM Settings → **QEMU** → **Input** → enable **USB sharing**
5. Optional: disable **USB 3.0 (XHCI)** if attach fails (use USB 2.0 hub/cable)
6. Start VM → toolbar **USB** icon → attach **candleLight USB to CAN adapter**
7. On guest: `lsusb` → `1d50:606f`, then `can-up.sh`, then `robot_discover.py`

You cannot flip an existing Apple VM to QEMU in place — backend is fixed per VM.

### Option B — Attach via CLI (QEMU VM only, while running)

```bash
utmctl list
utmctl usb list                    # find 1d50:606f
utmctl start "playbot-ubuntu-robot"   # or your VM name
utmctl usb connect "playbot-ubuntu-robot" "1d50:606f"
```

Repeat `usb connect` after each VM reboot (not permanent).

### Option C — Robot stack on Mac (workaround)

If you stay on Apple Virtualization only: run **lightsaber + CAN on macOS** next to the arm (plug candleLight into the **Mac**, not the VM). The repo supports this via python-can **`gs_usb`** + `can_platform.py`.

**Setup and commands:** [MAC-ROBOT.md](../MAC-ROBOT.md)

```bash
cd projects/lightsaber && source .venv/bin/activate
brew install libusb && pip install "python-can[gs-usb]"
python robot_discover.py
```

Less battle-tested than Linux SocketCAN; prefer VM/QEMU when you can pass USB through.

---

## After USB appears in the VM

```bash
bash ~/piper-vision-hackathon/projects/lightsaber/ubuntu_shared/can-up.sh
cd ~/piper-vision-hackathon/projects/lightsaber && source .venv/bin/activate
python robot_discover.py
```

Pass criteria: `[OK] USB-CAN adapter` → `[OK] can0` → `[OK] CAN frames` → `[OK] PiPER on bus`.

---

## Troubleshooting attach

| Symptom | Try |
|---------|-----|
| USB menu empty | VM must be **QEMU** + USB sharing on |
| “Cannot open USB device” | UTM in foreground; unplug/replug; release device from other apps |
| Device on Mac, never in VM | Wrong backend (Apple Virtualization) |
| Attach then no `can0` | `sudo modprobe gs_usb`; `dmesg \| tail`; `can-up.sh` |
| Hub issues | Plug candleLight **directly** into Mac (no hub) |

---

## Your adapter

| Field | Value |
|-------|--------|
| Name | candleLight USB to CAN adapter |
| USB ID | `1d50:606f` |
| Linux driver | `gs_usb` → `can0` |
| Bitrate | 1000000 (1 Mbps) for PiPER |
