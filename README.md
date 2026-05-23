# AI Lightsaber Trainer

Webcam vision → attack direction → PiPER block pose (stub by default).

## Quick start

```bash
cd projects/lightsaber
source .venv/bin/activate
python main.py
```

No camera? Set `USE_FAKE_ATTACKS = True` in `config.py`.

## Team ownership

| Developer | Branch | Owns |
|-----------|--------|------|
| **1 — Vision** | `feature/vision` | `camera.py`, `vision.py`, `overlays.py` |
| **2 — Robot** | `feature/robot` | `robot.py`, `poses.py`, `safety.py`, `movement_trainer.py` |
| **3 — App** | `feature/demo` | `main.py`, `dashboard.py`, `sounds.py`, `README.md` |

**Shared (coordinate before editing):** `contracts.py`, `config.py`, `requirements.txt`

## Architecture rule

All cross-team communication goes through **`contracts.py`**:

```python
direction: AttackDirection = vision.detect_attack(frame)
robot.respond_to_attack(direction)
```

Types: `AttackDirection`, `RobotPose`, protocols `AttackDetector`, `RobotController`.

## Safety defaults

- `DRY_RUN = True` in `config.py` — prints moves, no CAN motion
- Movement cooldown via `SafetyGuard`
- Emergency stop key: **`e`**

## Git workflow

- `main` stays stable
- One PR per feature branch; only touch owned files unless coordinating on `contracts.py`

## Milestone 1 checklist

- [ ] `python main.py` opens webcam (or fake attacks)
- [ ] Attack direction shown on overlay
- [ ] Robot prints intended pose
- [ ] Sound/dashboard hooks present (optional flags in `config.py`)
- [ ] `python -m unittest tests.test_contracts` passes

## Tests

```bash
python -m unittest tests.test_contracts
```
