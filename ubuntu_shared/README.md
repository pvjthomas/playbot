# UTM shared folder docs (Mac ↔ Ubuntu)

**Do not move, rename, or delete the real UTM share on the Mac.**

| | Path |
|--|------|
| **UTM shared directory (Mac)** | **`/Users/fio/UbuntuShared`** — configured in UTM → VM Settings → Sharing |
| **This folder** | `ubuntu_shared/` in the lightsaber repo (monorepo: `projects/lightsaber/ubuntu_shared/`) |

```
Mac UTM share:  /Users/fio/UbuntuShared/
Ubuntu (guest): mount path from UTM Sharing settings (see SSH-SETUP.md)
```

- **Not** the same as `projects/shared/` (Python deps / code shared across projects)
- **Versioned in git** at `ubuntu_shared/` in this repo (playbot / lightsaber)
- Monorepo checkout may also have `projects/ubuntu_shared/` as a sibling copy — keep in sync or use only this folder
- Vision/app git work: repo root on Mac; robot/CAN work on VM via SSH + the UTM share

**Docs in this folder:**

| File | Purpose |
|------|---------|
| **[MAC-QEMU-ROBOT-VM.md](MAC-QEMU-ROBOT-VM.md)** | **Mac → UTM QEMU → PiPER** (full setup guide) |
| [ENVIRONMENT.md](ENVIRONMENT.md) | Full Mac + UTM + Piper setup summary |
| [VM-ROBOT-CHECKLIST.md](VM-ROBOT-CHECKLIST.md) | Robot milestones after VM is up |
| [USB-PASSTHROUGH.md](USB-PASSTHROUGH.md) | Why Apple Virtualize cannot pass USB |
| [SSH-SETUP.md](SSH-SETUP.md) | SSH keys, config, troubleshooting |
| [CURSOR-REMOTE-SSH.md](CURSOR-REMOTE-SSH.md) | Cursor Remote SSH to the VM |

Agents: see repo `.cursor/rules.md`.
