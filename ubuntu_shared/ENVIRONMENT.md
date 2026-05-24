# Environment setup — Mac host + UTM Ubuntu robot VM

Living document for the **playbot / lightsaber** hackathon robot dev environment.

---

## Host machine (Mac)

| Item | Value |
|------|--------|
| Hardware | MacBook Pro, Apple Silicon **M4** |
| Virtualization | **UTM** |
| Guest OS | **Ubuntu Server 24.04 ARM64** |
| UTM backend | Apple Virtualization enabled — **no USB passthrough**; CAN needs **QEMU VM** ([USB-PASSTHROUGH.md](USB-PASSTHROUGH.md)) |
| Rosetta | Enabled (in UTM) |
| RAM | 8 GB |
| CPU | 6 cores |
| Storage | 64 GB |
| Shared directory | **Enabled** → Mac path **`/Users/fio/UbuntuShared`** (**do not move**) |

---

## Ubuntu VM

| Item | Value |
|------|--------|
| Hostname | **`ubuntu-robot`** |
| Username | **`philip`** |
| SSH | OpenSSH server installed and enabled |
| Network | DHCP (UTM shared network) |
| IP address | **`192.168.64.2`** (Apple Virt.) / **`192.168.64.4`** (QEMU robot VM — verify with `hostname -I`) |
| Architecture | **ARM64 native** (Apple Virtualization — **not** x86 emulation) |
| Docker | Not installed |
| ROS | Not installed yet |

### Installed packages (base)

```bash
sudo apt install -y git curl wget python3-pip can-utils net-tools
```

Also: `openssh-server` (for SSH from Mac).

---

## Robot hardware

| Item | Value |
|------|--------|
| Arm | **AgileX Piper** |
| Bus | **CAN** via USB CAN adapter |
| USB passthrough | Adapter passed from **macOS → Ubuntu VM** in UTM USB settings (not used on Mac for CAN) |

---

## Development workflow (planned)

1. **Mac** — vision/app dev, Cursor locally on `projects/lightsaber/`
2. **SSH** — `philip@192.168.64.2` from Mac terminal
3. **Cursor Remote SSH** — connect to `ubuntu-robot`, open code on VM (via shared mount or clone)
4. **Ubuntu VM** — live robot control, `piper_sdk`, CAN (`can0` @ 1 Mbps)
5. **File sync** — UTM shared folder `/Users/fio/UbuntuShared` (Mac ↔ guest mount)

---

## Current status

- [x] Ubuntu Server 24.04 ARM64 installed
- [x] System updated / upgraded
- [x] OpenSSH installed and enabled
- [x] Base packages: git, curl, wget, python3-pip, can-utils, net-tools
- [x] SSH from Mac terminal verified (`philip@192.168.64.2`)
- [ ] Cursor Remote SSH configured — see [CURSOR-REMOTE-SSH.md](CURSOR-REMOTE-SSH.md)
- [ ] USB CAN adapter attached to VM (UTM USB sharing)
- [ ] CAN interface verified (`ip link`, `can0` up @ 1000000)
- [x] `lightsaber` venv + tests on VM (`python -m unittest tests.test_contracts`)
- [x] `robot_smoke.py` DRY_RUN on VM
- [ ] USB CAN → VM; `can0` up (`can-up.sh`)
- [x] `piper_sdk` joint commands in `robot.move_to_pose()` (LIVE when `DRY_RUN=False`)
- [ ] **Deferred:** live vision overlay — Mac or VM desktop ([VM-ROBOT-CHECKLIST.md](VM-ROBOT-CHECKLIST.md))
- [ ] ROS 2 (optional — not required for current lightsaber stack)

---

## Next steps

1. SSH into VM from macOS: `ssh philip@192.168.64.2`
2. Setup **Cursor Remote SSH** (Host: `ubuntu-robot`, same IP/user)
3. Attach **USB CAN adapter** to VM in UTM (uncheck from Mac if needed)
4. Verify CAN: `ip link show`, `sudo ip link set can0 type can bitrate 1000000`, `sudo ip link set can0 up`
5. Install / run lightsaber on VM: `bash setup.sh`, `python main.py` (`DRY_RUN=True`)
6. Robot milestone: calibrate poses → enable hardware with team approval

See also:

- [SSH-SETUP.md](SSH-SETUP.md) — SSH config, keys, troubleshooting
- [README.md](README.md) — UTM shared folder rules
- [PLATFORM.md](../PLATFORM.md) — Mac vs Ubuntu roles
- [task-robot.md](../task-robot.md) — robot dev milestones

---

## Quick reference

```bash
# From Mac
ssh philip@192.168.64.2

# Recommended ~/.ssh/config on Mac
# Host ubuntu-robot
#   HostName 192.168.64.2
#   User philip
```

**Note:** Earlier notes used hostname `playbot-ubuntu-robot`; the VM hostname is **`ubuntu-robot`**. Use either as the SSH config `Host` alias — what matters is `HostName 192.168.64.2` and `User philip`.
