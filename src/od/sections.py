"""sections.py — daily-note markdown (pure functions, no I/O)

Purpose:
    Parse and modify note text: H1 sections, todo items, timestamped log
    lines, fenced code blocks. The daily-note conventions live here and
    only here.

Public:
    parse(text) -> Note
    append_to_section(note, heading, line, style) -> Note
    add_section(note, heading) -> Note
    open_tasks(note) -> list[Task]
    mark_done(note, n) -> Note
    render(note) -> str

Invariants:
    Pure — no file/network/subprocess I/O, fully unit-testable;
    render(parse(x)) == x for untouched sections (round-trip fidelity);
    style auto-detection (todo/log/plain) follows the conventions table in
    CLAUDE.md.

Depends on:
    stdlib only. The most parallel-safe module — hand to any agent in
    isolation.
"""
