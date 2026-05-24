# PiPER robot on macOS (direct CAN)

Use this when the **candleLight USB-CAN adapter** is plugged into the **Mac** and your UTM VM cannot see USB (Apple Virtualization). Vision + robot can both run on the Mac next to the arm.

> **SDK note:** AgileX’s newer **[pyAgxArm](https://github.com/agilexrobotics/pyAgxArm)** is the intended successor to **`piper_sdk`** and is supposed to support **Mac native** control (via serial/SLCAN CAN hardware in AgileX docs). **This repo uses `piper_sdk` + candleLight**, which does not work reliably on macOS — hence the Linux VM path in [ubuntu_shared/MAC-QEMU-ROBOT-VM.md](ubuntu_shared/MAC-QEMU-ROBOT-VM.md). Consider `pyAgxArm` when migrating off candleLight or when AgileX documents full Mac support for your adapter.

**Preferred for production:** Ubuntu VM or bare metal with SocketCAN (`can0`) — see [PLATFORM.md](PLATFORM.md) and [ubuntu_shared/USB-PASSTHROUGH.md](ubuntu_shared/USB-PASSTHROUGH.md).

---

## How it differs from Linux

| | Linux / VM | macOS (candleLight) |
|---|------------|---------------------|
| CAN stack | Kernel SocketCAN `can0` + `gs_usb` module | python-can **`gs_usb`** (userspace libusb) |
| `ip link` / `can-up.sh` | Required | **Not used** |
| piper_sdk default | `C_PiperInterface("can0")` | `CreateCanBus(bustype="gs_usb", judge_flag=False)` |
| Adapter visible | `lsusb` → `1d50:606f` | System Profiler — **yes** |
| Adapter usable | Usually **yes** | Often **`Errno 13` Access denied** (known issue) |

**Important:** AgileX documents macOS with a **serial SLCAN** module (`/dev/ttyACM0`), not the kit **candleLight** (SocketCAN). See [piper_sdk #24](https://github.com/agilexrobotics/piper_sdk/issues/24). For candleLight, **Linux is the reliable path** (QEMU UTM VM with USB passthrough).

**Preferred for production:** Ubuntu VM (QEMU) or bare metal with SocketCAN — see [USB-PASSTHROUGH.md](ubuntu_shared/USB-PASSTHROUGH.md).

---

## One-time setup (Mac — may still hit Access denied on candleLight)

From `projects/lightsaber` with venv active:

```bash
# USB backend for python-can (libusb)
brew install libusb

# gs_usb interface + pyusb
pip install "python-can[gs-usb]"

# Already in requirements.txt: piper_sdk, python-can
bash setup.sh
source .venv/bin/activate
```

Confirm the adapter on USB:

```bash
system_profiler SPUSBDataType | grep -A6 -i candle
```

---

## Discovery and smoke (on Mac, not in VM)

```bash
cd projects/lightsaber
source .venv/bin/activate

# Read-only: USB + gs_usb open + PiPER feedback (no motion)
python robot_discover.py

# Software-only poses (no CAN)
python robot_smoke.py

# LIVE connect only (no joint motion)
python robot_smoke.py --connect

# LIVE move — clear workspace, arm powered, teach mode off
python robot_smoke.py --live --pose HOME --i-know
```

Keep `DRY_RUN = True` in git. For a full app run with real motion:

```bash
# Terminal: set live mode for this session only
CAN_BUSTYPE=gs_usb python -c "import config; config.DRY_RUN=False"  # prefer editing config locally
```

Or temporarily set `DRY_RUN = False` in a **local** `config.py` (do not commit) and run:

```bash
python main.py --camera piper
```

---

## Config keys (`config.py`)

| Key | Mac typical value | Meaning |
|-----|-------------------|--------|
| `CAN_BUSTYPE` | `"auto"` → `gs_usb` | Force with `"gs_usb"` if needed |
| `CAN_CHANNEL` | `"auto"` → `"0"` | gs_usb device index (first adapter) |
| `CAN_BITRATE` | `1000000` | PiPER bus speed |
| `CAN_INTERFACE` | `can0` | Linux only; ignored for gs_usb connect |

Serial adapters (uncommon for this kit): `CAN_BUSTYPE = "slcan"`, `CAN_CHANNEL = "/dev/tty.usbmodem..."`, see piper_sdk `demo/V2/piper_set_can.py`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `[OK] candleLight` then `[FAIL] gs_usb … Access denied` | **Known on Mac** — candleLight + libusb often blocked; use **QEMU Linux VM** ([USB-PASSTHROUGH.md](ubuntu_shared/USB-PASSTHROUGH.md)) or AgileX **serial** CAN module |
| `No module named 'usb'` | `pip install "python-can[gs-usb]"` |
| `Cannot import ... gs_usb` | `brew install libusb`, replug adapter |
| UTM holding device | Quit UTM or detach USB from VM, replug to Mac |
| Works on Mac, not in VM | Expected with Apple Virtualization — use QEMU VM |

---

## Code entry points

- **`can_platform.py`** — `resolve_can_profile()`, `connect_piper_interface()`
- **`robot.py`** — uses `can_platform` for LIVE connect
- **`robot_discover.py`** — Mac vs Linux checks
- **`robot_smoke.py`** — `--probe-can` uses gs_usb on Darwin

References: [python-can gs_usb](https://python-can.readthedocs.io/en/stable/interfaces/gs_usb.html), [piper_sdk macOS discussion](https://github.com/agilexrobotics/piper_sdk/issues/24).
