# Task — App / Demo (Developer 3)

**Project:** this repo (`lightsaber`)  
**Branch:** `feature/demo`  
**Owns:** `main.py`, `dashboard.py`, `sounds.py`, `README.md`

Wire vision + robot through **`contracts.py` only**. Do not import vision internals into robot or vice versa.

---

## Setup

```bash
cd projects/lightsaber   # or your clone path
git checkout -b feature/demo    # first time only
source .venv/bin/activate
bash setup.sh              # if .venv missing
python main.py
python -m unittest tests.test_contracts
```

Camera flags: see **[task-vision.md](task-vision.md)** (`--camera piper`, `--camera laptop`, etc.).

---

## Milestone 1 — Runnable demo (current sprint)

- [ ] `main.py` loop: frame → `detect_attack` → `respond_to_attack`
- [ ] Webcam preview window with overlay
- [ ] Keys work: **`q`** quit, **`e`** emergency stop, **`h`** home
- [ ] `sounds.py` stub prints on attack (`ENABLE_SOUNDS = False` default)
- [ ] `dashboard.py` stub optional (`ENABLE_DASHBOARD = False` default)
- [ ] Update `README.md` with run instructions for all 3 devs

**Done when:** `python main.py` runs end-to-end with robot printing moves and overlay visible.

---

## Milestone 2 — Sounds + dashboard

- [ ] Add `assets/sounds/` in this repo (or use monorepo `../assets/sounds/`) — whoosh, block, clash stubs
- [ ] `ENABLE_SOUNDS = True`: pygame plays per `AttackDirection`
- [ ] Dashboard: on-screen status panel or richer console summary
- [ ] `config.py` flags documented in README
- [ ] Handle camera permission errors gracefully (helpful message)

---

## Milestone 3 — Demo polish

- [ ] Title screen or idle `HOME` pose on start
- [ ] Strike counter / session stats in dashboard
- [ ] Demo mode: `USE_FAKE_ATTACKS = True` for presentations without camera
- [ ] Record short demo GIF instructions in README
- [ ] PR to `feature/demo` — **only** owned files (+ app keys in `config.py`)

---

## Contract wiring (main.py)

```python
direction = vision.detect_attack(frame)
robot.respond_to_attack(direction)
sounds.play_for_attack(direction)
dashboard.update(direction, robot.current_pose, fps)
```

---

## Git / PR

- Keep **`main`** stable — merge via PR only
- One branch per feature; avoid editing vision/robot files unless coordinating
- Shared edits (`contracts.py`, `config.py`) → short team sync first

---

## Coordination

- New keyboard shortcuts → document in README + notify team
- If vision or robot API changes → they update `contracts.py` first, then you pull
