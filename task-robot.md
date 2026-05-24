# Task — Robot (Developer 2)

**Project:** this repo (`lightsaber`)  
**Branch:** `feature/robot`  
**Owns:** `robot.py`, `poses.py`, `safety.py`, `movement_trainer.py`

Do **not** import `vision`, `camera`, or `overlays`. Integrate only through `contracts.py` (`RobotPose`, `RobotController`, `pose_for_attack`).

**Partner motion semantics:** **[DIRECTIONS.md](DIRECTIONS.md)** — body left/right, centerline blocks, withdraw vs strike (summary below).

---

## Partner motion → robot response (required)

Vision labels use **body cross-body direction** (partner facing the camera), not screen-edge compass. See **DIRECTIONS.md**.

### Four partner motions (two direction labels × two roles)

`AttackDirection` is still **`left` | `right`** (plus `high`, `center`, `none`). **Role** is separate — eval logs it as `motion_role`; live `SwingState` will gain intent later.

| Role | `expected_direction` | Partner motion | Robot must |
|------|----------------------|----------------|------------|
| **Attack left** | `left` | RIGHT arm: travel **partner’s right → partner’s left**; strike **stops at centerline** (robot blocks there) | Block at **midline** — **`GUARD_CENTER`** (see below) |
| **Attack right** | `right` | LEFT arm: travel **partner’s left → partner’s right**; stop at **centerline** | **`GUARD_CENTER`** |
| **Withdraw right** | `right` | From centerline (after **left** attack blocked), retreat toward **partner’s right** | **Hold block** — stay on **`GUARD_CENTER`**; **do not** treat as a new `right` attack / `BLOCK_RIGHT` |
| **Withdraw left** | `left` | From centerline (after **right** attack blocked), retreat toward **partner’s left** | **Hold block** — stay on **`GUARD_CENTER`**; **do not** treat as a new `left` attack / `BLOCK_LEFT` |

**Pairing after a block:** left strike blocked → partner withdraws **right**; right strike blocked → partner withdraws **left**.

### Centerline blocking (default sparring)

- Partner cross-body **left/right** strikes are **stopped at the midline**, not full extension to the side.
- Robot arm presents **`GUARD_CENTER`** across the centerline to stop the saber (calibrate this pose on hardware first).
- Legacy mapping in `contracts.py` (`left` → `BLOCK_LEFT`, `right` → `BLOCK_RIGHT`) remains for **full-extension** drills; **centerline sparring overrides** to **`GUARD_CENTER`** for side strikes until intent is wired (below).

### When to move (timing)

Vision drives temporal phases (`begin` → `mid` → `end`). **Robot must react before `end`.**

| Phase | Robot use |
|-------|-----------|
| **`begin`** | Travel direction visible (wind-up + velocity). **Primary block window** — move to `GUARD_CENTER` (or block pose) on first confident **`left`/`right`/`high`/`center`**. |
| **`mid`** | Confirm / hold block while partner still moving into centerline. |
| **`end`** | Partner stopped at block. **Confirm pose only** — direction was latched in begin/mid; **do not** re-parse stop location as a new attack. |
| **`idle`** | Between reps — `HOME` or relaxed guard per app policy. |

Today `main.py` calls `respond_to_attack(direction)` on begin/mid/end via `swing_trigger.py`. **Use `swing.direction` as the latched travel direction**, not a fresh END-pose guess.

### Withdraw vs attack (robot policy)

Until `MotionIntent` is on `SwingState`:

- If partner was just blocked at centerline and velocity reverses (withdraw), **do not** command `BLOCK_LEFT` / `BLOCK_RIGHT` for the retreat direction.
- **Hold `GUARD_CENTER`** through withdraw, or return to `HOME` after a cooldown when vision returns **`idle`**.
- Vision eval: `--centerline` sessions log `motion_role: "strike" | "withdraw"` and `follows_strike` per trial.

### Proposed contract extension (coordinate before implementing)

```python
MotionIntent = Literal["none", "strike", "withdraw"]

@dataclass(frozen=True)
class SwingState:
    direction: AttackDirection   # travel: left/right/…
    phase: SwingPhase
    kind: MotionKind
    intent: MotionIntent = "strike"  # withdraw = post-block retreat
    ...
```

Robot API (Milestone 3+):

```python
def respond_to_swing(self, swing: SwingState) -> None:
    """Block on strike+begin/mid; hold GUARD on withdraw; ignore end re-labels."""
```

Until then: **`respond_to_attack(left|right)`** on begin/mid only for strikes; treat rapid opposite motion after centerline block as withdraw (hold pose).

### Pose calibration priority

1. **`GUARD_CENTER`** — midline block (centerline sparring)
2. **`HOME`** — between reps
3. **`BLOCK_LEFT` / `BLOCK_RIGHT`** — full-extension blocks (optional / legacy drills)
4. **`BLOCK_HIGH`**, **`GUARD_CENTER`** thrust stop for **`center`**

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
**VM smoke (software):** `python robot_smoke.py` — see **[ubuntu_shared/VM-ROBOT-CHECKLIST.md](ubuntu_shared/VM-ROBOT-CHECKLIST.md)**.

**VM setup (Mac host):** **[ubuntu_shared/MAC-QEMU-ROBOT-VM.md](ubuntu_shared/MAC-QEMU-ROBOT-VM.md)** — UTM QEMU, USB candleLight, `can0`, discover/smoke.

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
- [ ] Calibrate: **`GUARD_CENTER`** (midline block — **first** for centerline sparring), then `HOME`
- [ ] Calibrate: `BLOCK_LEFT`, `BLOCK_RIGHT`, `BLOCK_HIGH` for full-extension / legacy drills
- [ ] `movement_trainer.py`: step through pose list slowly (still stub/print OK)
- [ ] Verify no collisions at table height
- [ ] Document which pose is used for centerline vs full-extension blocks in `poses.py` comments

**Only after human approval:**

- [ ] Wire `piper_sdk` joint commands in `robot.move_to_pose()`
- [ ] Set `DRY_RUN = False` locally for controlled tests (never commit `False` to `main`)

---

## Milestone 3 — Live sparring response

- [ ] CAN connect on Linux (`C_PiperInterface`, `can0`, 1 Mbps)
- [ ] `connect()` / `disconnect()` lifecycle solid
- [ ] **Centerline sparring:** on `left`/`right` strike in **`begin`/`mid`**, move to **`GUARD_CENTER`** (not full `BLOCK_*` unless configured for legacy mode)
- [ ] **Hold block** through partner **withdraw** after centerline stop — no opposite `BLOCK_*` on retreat
- [ ] **`end` phase:** hold / confirm only — do not re-trigger on stop pose
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
- **`MotionIntent` (`strike` / `withdraw`)** on `SwingState` — agree with vision before robot branches on withdraw
- Vision eval for centerline + withdraw: `python collect_swing_eval.py --centerline …`
- Mac: use [MAC-ROBOT.md](MAC-ROBOT.md) (`gs_usb`) when VM cannot see USB; Linux VM still preferred for CAN
