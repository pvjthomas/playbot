# Task — Robot (Developer 2)

**Project:** this repo (`lightsaber`)  
**Branch:** `feature/robot`  
**Owns:** `robot.py`, `poses.py`, `safety.py`, `movement_trainer.py`

Do **not** import `vision`, `camera`, or `overlays`. Integrate only through `contracts.py` (`RobotPose`, `RobotController`, `pose_for_attack`).

---

## Setup

```bash
cd projects/lightsaber   # or your clone path
git checkout -b feature/robot    # first time only
source .venv/bin/activate
python main.py          # DRY_RUN — robot prints intended moves
python -m unittest tests.test_contracts
```

**VM step 1 (device, no motion):** `python robot_discover.py`  
**VM smoke (software):** `python robot_smoke.py` — see **`projects/ubuntu_shared/VM-ROBOT-CHECKLIST.md`**.

Platform notes: **[PLATFORM.md](PLATFORM.md)** — live CAN on Ubuntu; Mac vision dev uses `DRY_RUN`. **Mac robot (no VM USB):** [MAC-ROBOT.md](MAC-ROBOT.md). UTM share: **`/Users/fio/UbuntuShared`** (never move).

---

## Milestone 1 — Stub movement (current sprint)

- [ ] `respond_to_attack(direction)` maps via `pose_for_attack()` and prints pose
- [ ] `move_to_pose(name)` works for all poses in `poses.py`
- [ ] `emergency_stop()` blocks further moves (`safety.py`)
- [ ] `DRY_RUN = True` stays default in `config.py`
- [ ] Movement cooldown respected (`MOVEMENT_COOLDOWN_SEC`)

**Done when:** vision dev triggers attacks and terminal shows e.g. `[robot] DRY_RUN → BLOCK_LEFT: J=[...]`

---

## Milestone 2 — Calibrate poses on hardware

- [ ] Jog arm manually; record real joint angles into `poses.py`
- [ ] Calibrate: `HOME`, `BLOCK_LEFT`, `BLOCK_RIGHT`, `BLOCK_HIGH` first
- [ ] `movement_trainer.py`: step through pose list slowly (still stub/print OK)
- [ ] Verify no collisions at table height

**Only after human approval:**

- [ ] Wire `piper_sdk` joint commands in `robot.move_to_pose()`
- [ ] Set `DRY_RUN = False` locally for controlled tests (never commit `False` to `main`)

---

## Milestone 3 — Live sparring response

- [ ] CAN connect on Linux (`C_PiperInterface`, `can0`, 1 Mbps)
- [ ] `connect()` / `disconnect()` lifecycle solid
- [ ] `DODGE_BACK`, `COUNTER_TAP` poses tuned (optional demo flair)
- [ ] Emergency stop tested with **`e`** key from `main.py`
- [ ] PR to `feature/robot` — **only** owned files (+ robot keys in `config.py`)

---

## Contract you must implement

```python
class PiperRobot:
    def respond_to_attack(self, direction: AttackDirection) -> None: ...
    def move_to_pose(self, name: RobotPose) -> None: ...
    def emergency_stop(self) -> None: ...
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
```

---

## Safety rules (non-negotiable)

- Default **DRY_RUN = True**
- No hardware motion without explicit team + human sign-off
- Cooldown always on
- Emergency stop must halt motion immediately when live

---

## Coordination

- New pose names → update **`contracts.py`** `RobotPose` + `ATTACK_TO_POSE` with team
- Mac: use [MAC-ROBOT.md](MAC-ROBOT.md) (`gs_usb`) when VM cannot see USB; Linux VM still preferred for CAN
