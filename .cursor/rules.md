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

## Git — Philip (pvjthomas)

Philip uses GitHub’s private noreply address for all commits in this repo (required while **Block command line pushes that expose my email** is on):

- **Name:** `pvjthomas`
- **Email:** `150876472+pvjthomas@users.noreply.github.com`

Repo-local config (already set in `projects/lightsaber`):

```bash
git config user.name "pvjthomas"
git config user.email "150876472+pvjthomas@users.noreply.github.com"
```

When creating commits for Philip, use this identity. Do not use personal Gmail in commit author/committer fields. If a push is rejected with GH007, amend with `--reset-author` using the noreply email above.
