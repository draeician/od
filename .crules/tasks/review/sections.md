# Task: sections.py — daily-note markdown (pure functions, no I/O)

Wave: 1

## Module
`src/od/sections.py`

## Purpose
Parse and modify note text: H1 sections, todo items, timestamped log
lines, fenced code blocks. The daily-note conventions live here and only
here.

## Public Interface
- `parse(text) -> Note`
- `append_to_section(note, heading, line, style) -> Note`
- `add_section(note, heading) -> Note`
- `open_tasks(note) -> list[Task]`
- `mark_done(note, n) -> Note`
- `render(note) -> str`

## Acceptance Criteria
- [x] Pure functions only — no file, network, or subprocess I/O.
- [x] Fully unit-testable in isolation.
- [x] `render(parse(x)) == x` holds for untouched sections (round-trip fidelity).
- [x] Style auto-detection (todo/log/plain) follows the conventions table in CLAUDE.md.
- [x] Tests added in `tests/test_sections.py`.

## Depends On
stdlib only (most parallel-safe module — hand to any agent in isolation).

## Coder Notes

Implemented Wave 1 `sections` only (`src/od/sections.py` + `tests/test_sections.py`).

- **Types:** frozen `Note` / `Section` / `Task`; typed errors `SectionsError`,
  `DuplicateHeadingError`, `TaskIndexError`, `UnknownStyleError`.
- **Parse/render:** H1-only section boundaries (`#`, not `##`); preamble
  (`heading is None`) preserved; trailing-newline flag for exact round-trip.
- **Styles:** `auto|todo|log|plain|code`. Auto scans newest non-empty body
  line for checkbox / log pattern; empty section → plain. Log lines:
  `- YYYY-MM-DD HH:MM :message` via `datetime.now()`. Code wraps in fences.
- **Unknown heading on append:** creates new H1 at end (conventions).
- **Tasks:** open tasks are `- [ ] …` only, 1-based document order for
  `mark_done`; completed as `- [x] …`.
- **Verification:** `PYTHONPATH=src .venv/bin/python -m pytest tests/test_sections.py -v` → 33 passed.
- **Not touched:** any other `src/od/*` module.
