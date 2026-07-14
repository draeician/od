# Git, versioning, and release

Follow `.crules/modes/GIT_POLICY.md` in full when present.

## Conventional commits

`feat` | `fix` | `docs` | `chore` | `refactor` — imperative subject, ≤72 chars.

## Version sources (must match)

1. `pyproject.toml` — **master** (`[project].version`)
2. `src/od/__init__.py` — runtime constant (`__version__`)
3. Git tags on release (`vX.Y.Z`)

Bump from the highest observed value (monotonic). Default: feat→minor,
fix/docs/chore/refactor→patch, breaking→major.

## Pre-commit

- Heuristic secret scan on staged files.
- No credentials or private dumps committed (including real vault content).
- After version edit, verify:
  `PYTHONPATH=src python3 -c "from od import __version__; print(__version__)"`
  and confirm it matches `pyproject.toml`.

## Shortcuts

User says **commit** / **branch** / **release** → Manager persona + `GIT_POLICY.md`.
