# SSH into UTM Ubuntu — `ubuntu-robot`

Plan for connecting from your **Mac** to the **UTM Ubuntu** robot VM. Full environment details: **[ENVIRONMENT.md](ENVIRONMENT.md)**.

| Item | Value |
|------|--------|
| Hostname | `ubuntu-robot` |
| IP (UTM shared network) | `192.168.64.2` |
| User | `philip` |
| Shared folder (Mac) | **`/Users/fio/UbuntuShared`** — **do not move** |

---

## Phase 1 — One-time setup on the VM (inside Ubuntu)

Do this in the UTM console or after first local login.

### 1.1 Install and enable SSH

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable ssh
sudo systemctl start ssh
sudo systemctl status ssh    # should be active (running)
```

### 1.2 Confirm user and hostname

```bash
whoami                       # expect: philip
hostname                     # expect: ubuntu-robot (or set below)
sudo hostnamectl set-hostname ubuntu-robot
```

### 1.3 Get the VM IP (verify `192.168.64.2`)

```bash
ip -4 addr show
# or
hostname -I
```

UTM **Shared Network** usually gives `192.168.64.x`. If the IP changes after reboot, use `hostname` + Mac `~/.ssh/config` (Phase 2) and update `HostName` when needed.

### 1.4 Firewall (if ufw is enabled)

```bash
sudo ufw allow OpenSSH
sudo ufw status
```

---

## Phase 2 — Mac: SSH config (recommended)

On your Mac, edit `~/.ssh/config`:

```
Host playbot-ubuntu-robot ubuntu-robot
  HostName 192.168.64.2
  User philip
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking accept-new
```

Then connect with:

```bash
ssh playbot-ubuntu-robot
# or: ssh philip@192.168.64.2
```

---

## Phase 3 — SSH keys (no password every time)

On **Mac** (if you do not already have a key):

```bash
ssh-keygen -t ed25519 -C "philip@mac-lightsaber" -f ~/.ssh/id_ed25519
```

Copy key to the VM (VM must be running and reachable):

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub philip@192.168.64.2
# or, if config exists:
ssh-copy-id ubuntu-robot
```

Test:

```bash
ssh ubuntu-robot 'echo OK && uname -a'
```

---

## Phase 4 — UTM shared folder (`UbuntuShared`)

On **Mac**, the folder must stay at:

```
/Users/fio/UbuntuShared/
```

In **UTM** → VM settings → Sharing (or VirtFS):

- Share that Mac path into the guest
- Note the **guest mount path** (common examples: `/mnt/UbuntuShared`, `/media/psf/UbuntuShared`, or a path under `/home/philip/...`)

On the **VM**, verify the mount:

```bash
mount | grep -i shared
ls -la /path/to/mounted/UbuntuShared
```

The share may contain a workspace file pointing at the monorepo. Lightsaber code on the VM is typically:

```
.../piper-vision-hackathon/projects/lightsaber/
```

(via the shared mount or a git clone inside the share)

**Do not move `/Users/fio/UbuntuShared` on the Mac** — UTM points at this exact path.

---

## Phase 5 — Robot dev environment on the VM

After SSH in:

```bash
# Go to lightsaber (adjust path to your mount or clone)
cd ~/piper-vision-hackathon/projects/lightsaber   # shared mount
# OR clone if not mounted:
# git clone https://github.com/pvjthomas/playbot.git
# cd playbot/projects/lightsaber

git checkout feature/robot    # or main
bash setup.sh
source .venv/bin/activate
python -m unittest tests.test_contracts
```

### CAN (when USB-CAN is passed through to the VM)

UTM must **USB-share** the CAN adapter to Linux (not Mac). Then on the VM:

```bash
ip link show                  # look for can0
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
```

Keep `DRY_RUN = True` in `config.py` until poses are calibrated. See [task-robot.md](../task-robot.md).

### Vision on Linux (Piper camera)

```bash
python camera.py --list
python vision.py --camera piper --camera-backend opencv
```

Linux Piper uses `/dev/video*` — fast OpenCV path (no ffmpeg workaround).

---

## Phase 6 — Daily workflow (Mac → VM)

1. Start UTM VM `ubuntu-robot`
2. From Mac terminal:

   ```bash
   ssh ubuntu-robot
   ```

3. Optional: **Cursor Remote SSH** — connect to `ubuntu-robot`, open the mounted `lightsaber` folder
4. Pull latest, run robot tests, enable CAN when ready

---

## Troubleshooting

| Problem | Check |
|---------|--------|
| `Connection refused` | `sudo systemctl start ssh` on VM; VM powered on |
| `No route to host` / timeout | UTM network = Shared Network; verify IP with `hostname -I` on VM |
| IP changed | Update `HostName` in `~/.ssh/config` |
| Permission denied (publickey) | Re-run `ssh-copy-id`; check `~/.ssh/authorized_keys` on VM |
| CAN not visible | USB device forwarded to Linux in UTM, not Mac |
| No shared files | UTM sharing enabled; confirm guest mount path |

### Ping test from Mac

```bash
ping -c 3 192.168.64.2
```

---

## Checklist

- [ ] `openssh-server` running on VM
- [ ] `philip@192.168.64.2` login works
- [ ] `~/.ssh/config` entry `ubuntu-robot`
- [ ] SSH key installed (`ssh-copy-id`)
- [ ] `/Users/fio/UbuntuShared` mounted in guest (path documented)
- [ ] `lightsaber` venv + tests pass on VM
- [ ] CAN adapter passed through to VM (when doing hardware)

---

## Related docs

- [ENVIRONMENT.md](ENVIRONMENT.md) — Mac + VM + robot hardware summary
- [PLATFORM.md](../PLATFORM.md) — Mac vs Ubuntu roles
- [task-robot.md](../task-robot.md) — robot milestones
