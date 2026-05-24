# Cursor Remote SSH → `playbot-ubuntu-robot`

Connect Cursor on your Mac to the UTM Ubuntu VM for robot / CAN development.

| Item | Value |
|------|--------|
| UTM VM name | **`playbot-ubuntu-robot`** |
| SSH host alias | **`playbot-ubuntu-robot`** (also `ubuntu-robot`) |
| IP | `192.168.64.2` |
| User | `philip` |
| Mac UTM share | **`/Users/fio/UbuntuShared`** (do not move) |
| VM | Ubuntu Server 24.04 ARM64 |

Mac-side SSH config: `~/.ssh/config` (already set up).

---

## Before connecting

1. **Start the UTM VM** — Cursor cannot connect if the VM is off or paused.
2. Test from Mac terminal:

   ```bash
   ssh philip@192.168.64.2 'echo OK && hostname && uname -m'
   # or:
   ssh playbot-ubuntu-robot 'echo OK && hostname && uname -m'
   ```

   Expect: `OK`, hostname (`ubuntu-robot` or similar), and `aarch64`.

3. If password is prompted every time, install your SSH key once:

   ```bash
   ssh-copy-id playbot-ubuntu-robot
   ```

---

## Connect in Cursor

1. Open **Cursor** on the Mac.
2. `Cmd + Shift + P` → **Remote-SSH: Connect to Host…**
3. Choose **`playbot-ubuntu-robot`** or enter `philip@192.168.64.2`
4. A new Cursor window opens connected to the VM.
5. **File → Open Folder** and pick lightsaber on the VM, e.g.:
   - Guest mount of **`/Users/fio/UbuntuShared`** → `.../piper-vision-hackathon/projects/lightsaber/`
   - Or a git clone under `~/playbot/projects/lightsaber`

---

## Recommended folder to open

After SSH connect, find the shared mount on the VM:

```bash
mount | grep -i shared
ls /media /mnt ~ 2>/dev/null
```

Then in Cursor: **Open Folder** → `projects/lightsaber` under that mount.

Or clone once on the VM:

```bash
cd ~
git clone https://github.com/pvjthomas/playbot.git
cd playbot/projects/lightsaber
git checkout feature/vision
bash setup.sh
```

---

## Python / terminal in remote window

In the remote Cursor window:

```bash
source .venv/bin/activate
python main.py
python -m unittest tests.test_contracts
```

Cursor may prompt to install the **Python** extension on the remote — accept.

Set interpreter: `.venv/bin/python` (Command Palette → **Python: Select Interpreter**).

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `No route to host` | Start UTM VM (not paused); confirm IP with `hostname -I` on VM |
| Host not in list | Reload Cursor; check `~/.ssh/config` has `Host playbot-ubuntu-robot` |
| Permission denied | Run `ssh-copy-id playbot-ubuntu-robot` from Mac |
| Wrong architecture packages | VM is **ARM64** — use aarch64 wheels / `setup.sh` on VM, not Mac venv |
| USB CAN not visible | Pass USB device to VM in UTM, not Mac |
| Share files missing | UTM Sharing must point at **`/Users/fio/UbuntuShared`** on Mac |

---

## Related

- [ENVIRONMENT.md](ENVIRONMENT.md) — full Mac + VM setup
- [SSH-SETUP.md](SSH-SETUP.md) — keys and SSH details
