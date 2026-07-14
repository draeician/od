# Decisions

## 2026-07-14 — Hold SemVer bumps until release

Version strings stay at the scaffold value (`0.1.0`) through feature work.
Bump only when the human requests a **release** (tag / publish), not on each
`feat` commit. Runtime and metadata versions must still match when a release
bump happens.

## 2026-07-14 — Wave 1 module 1 was `sections`

First implementation task in wave 1 was `sections.py` (first listed in the
module-map build table).
