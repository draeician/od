# Decisions

## 2026-07-14 — Release 0.2.0 (lift hold)

Human requested **release bump**. SemVer hold at `0.1.0` ends for this cut.
Bumped to **0.2.0** (minor: cumulative `feat` waves 1–4). Tag: `v0.2.0`.
`pyproject.toml` and `src/od/__init__.py` must stay identical.

Ongoing policy: still prefer not bumping on every intermediate `feat` commit
while a multi-module wave is open; bump on explicit release (or when the human
asks). Runtime and metadata versions must match on every release commit.

## 2026-07-14 — Hold SemVer bumps until release

Version strings stay at the scaffold value (`0.1.0`) through feature work.
Bump only when the human requests a **release** (tag / publish), not on each
`feat` commit. Runtime and metadata versions must still match when a release
bump happens.

_Superseded for the 0.2.0 cut by “Release 0.2.0 (lift hold)” above._

## 2026-07-14 — Wave 1 module 1 was `sections`

First implementation task in wave 1 was `sections.py` (first listed in the
module-map build table).
