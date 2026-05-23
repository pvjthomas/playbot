# AI Lightsaber Trainer — team rules

## Ownership

| Area | Files | Branch |
|------|-------|--------|
| Vision | `camera.py`, `vision.py`, `overlays.py` | `feature/vision` |
| Robot | `robot.py`, `poses.py`, `safety.py`, `movement_trainer.py` | `feature/robot` |
| App | `main.py`, `dashboard.py`, `sounds.py`, `README.md` | `feature/demo` |
| Shared | `contracts.py`, `config.py` | coordinate via PR |

## Architecture

- **All cross-team imports go through `contracts.py` only.**
- Do not import `vision` from `robot` or vice versa.
- `main.py` wires modules together.

## Safety

- `DRY_RUN=True` by default
- Ask before enabling hardware in `config.py`
- Never delete files automatically

## PRs

- Touch only owned files unless updating `contracts.py` with team agreement
- Keep `main` branch stable
