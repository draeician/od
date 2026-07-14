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
- [ ] Pure functions only — no file, network, or subprocess I/O.
- [ ] Fully unit-testable in isolation.
- [ ] `render(parse(x)) == x` holds for untouched sections (round-trip fidelity).
- [ ] Style auto-detection (todo/log/plain) follows the conventions table in CLAUDE.md.
- [ ] Tests added in `tests/test_sections.py`.

## Depends On
stdlib only (most parallel-safe module — hand to any agent in isolation).
