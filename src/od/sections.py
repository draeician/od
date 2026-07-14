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

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

__all__ = [
    "SectionsError",
    "DuplicateHeadingError",
    "TaskIndexError",
    "UnknownStyleError",
    "Note",
    "Section",
    "Task",
    "parse",
    "render",
    "append_to_section",
    "add_section",
    "open_tasks",
    "mark_done",
]

Style = Literal["auto", "todo", "log", "plain", "code"]

_OPEN_TASK_RE = re.compile(r"^- \[ \] (.*)$")
_DONE_TASK_RE = re.compile(r"^- \[[xX]\] (.*)$")
_LOG_LINE_RE = re.compile(r"^- \d{4}-\d{2}-\d{2} \d{2}:\d{2} :")


class SectionsError(Exception):
    """Base error for daily-note section operations."""


class DuplicateHeadingError(SectionsError):
    """Raised when add_section targets an H1 that already exists."""


class TaskIndexError(SectionsError):
    """Raised when mark_done receives an out-of-range open-task index."""


class UnknownStyleError(SectionsError):
    """Raised when append_to_section is given an unsupported style."""


@dataclass(frozen=True)
class Section:
    """One H1 section, or the preamble (heading is None)."""

    heading: str | None
    lines: tuple[str, ...]


@dataclass(frozen=True)
class Note:
    """Parsed daily note: ordered sections plus trailing-newline flag."""

    sections: tuple[Section, ...]
    ends_with_newline: bool = False


@dataclass(frozen=True)
class Task:
    """An open checkbox task, numbered 1-based across the whole note."""

    index: int
    text: str
    heading: str


def _is_h1(line: str) -> bool:
    """Return True for ATX H1 lines (`# …`), not H2+ (`## …`)."""
    return line.startswith("#") and not line.startswith("##")


def _heading_text(line: str) -> str:
    """Extract H1 title text from an H1 source line."""
    if line.startswith("# "):
        return line[2:]
    if line == "#":
        return ""
    return line[1:]


def parse(text: str) -> Note:
    """Parse daily-note markdown into a Note.

    Only ATX H1 headings (`#`, not `##`) start sections. Content before
    the first H1 is a preamble section with ``heading is None``.
    """
    ends_with_newline = bool(text) and text.endswith("\n")
    lines = text.splitlines()
    sections: list[Section] = []
    current_heading: str | None = None
    body: list[str] = []
    in_preamble = True

    for line in lines:
        if _is_h1(line):
            if in_preamble:
                if body:
                    sections.append(Section(heading=None, lines=tuple(body)))
                in_preamble = False
            else:
                sections.append(
                    Section(heading=current_heading, lines=tuple(body))
                )
            current_heading = _heading_text(line)
            body = []
        else:
            body.append(line)

    if in_preamble:
        if body:
            sections.append(Section(heading=None, lines=tuple(body)))
    else:
        sections.append(Section(heading=current_heading, lines=tuple(body)))

    return Note(sections=tuple(sections), ends_with_newline=ends_with_newline)


def render(note: Note) -> str:
    """Serialize a Note back to markdown text.

    Round-trip invariant: ``render(parse(x)) == x`` for any input string.
    """
    if not note.sections:
        return "\n" if note.ends_with_newline else ""

    out: list[str] = []
    for section in note.sections:
        if section.heading is not None:
            out.append(f"# {section.heading}")
        out.extend(section.lines)
    result = "\n".join(out)
    if note.ends_with_newline:
        result += "\n"
    return result


def _detect_style(section: Section) -> Style:
    """Infer todo/log/plain from existing section body (newest first)."""
    for line in reversed(section.lines):
        stripped = line.strip()
        if not stripped:
            continue
        if _OPEN_TASK_RE.match(stripped) or _DONE_TASK_RE.match(stripped):
            return "todo"
        if _LOG_LINE_RE.match(stripped):
            return "log"
        # Fenced blocks and other content do not force "code" for free text.
        return "plain"
    return "plain"


def _format_entry(line: str, style: Style) -> tuple[str, ...]:
    """Format a user entry into one or more body lines for the given style."""
    if style == "todo":
        return (f"- [ ] {line}",)
    if style == "log":
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        return (f"- {ts} :{line}",)
    if style == "plain":
        if line.startswith("- ") or line.startswith("-"):
            return (line,)
        return (f"- {line}",)
    if style == "code":
        content = line.rstrip("\n")
        return ("```", *content.split("\n"), "```")
    raise UnknownStyleError(f"unknown style: {style!r}")


def add_section(note: Note, heading: str) -> Note:
    """Append a new empty H1 section. Raises if the heading already exists."""
    if any(s.heading == heading for s in note.sections):
        raise DuplicateHeadingError(f"heading already exists: {heading!r}")
    new_section = Section(heading=heading, lines=())
    return Note(
        sections=note.sections + (new_section,),
        ends_with_newline=True,
    )


def append_to_section(
    note: Note,
    heading: str,
    line: str,
    style: str = "auto",
) -> Note:
    """Append a formatted line under *heading*.

    Unknown headings create a new H1 section at the end of the note.
    *style* is one of auto|todo|log|plain|code. ``auto`` inspects the
    section body (todo / log / plain per CLAUDE.md conventions).
    """
    if style not in ("auto", "todo", "log", "plain", "code"):
        raise UnknownStyleError(f"unknown style: {style!r}")

    idx = next(
        (i for i, s in enumerate(note.sections) if s.heading == heading),
        None,
    )
    if idx is None:
        note = add_section(note, heading)
        idx = len(note.sections) - 1

    section = note.sections[idx]
    resolved: Style
    if style == "auto":
        resolved = _detect_style(section)
    else:
        resolved = style  # type: ignore[assignment]

    entry = _format_entry(line, resolved)
    new_lines = section.lines + entry
    new_section = Section(heading=section.heading, lines=new_lines)
    sections = list(note.sections)
    sections[idx] = new_section
    return Note(sections=tuple(sections), ends_with_newline=True)


def open_tasks(note: Note) -> list[Task]:
    """Return open checkbox tasks (``- [ ] …``) in document order, 1-based."""
    tasks: list[Task] = []
    index = 0
    for section in note.sections:
        for line in section.lines:
            match = _OPEN_TASK_RE.match(line)
            if match is None:
                continue
            index += 1
            tasks.append(
                Task(
                    index=index,
                    text=match.group(1),
                    heading=section.heading if section.heading is not None else "",
                )
            )
    return tasks


def mark_done(note: Note, n: int) -> Note:
    """Mark the *n*th open task (1-based, document order) as completed."""
    open_count = len(open_tasks(note))
    if n < 1 or n > open_count:
        raise TaskIndexError(
            f"open task index out of range: {n} (open tasks: {open_count})"
        )

    seen = 0
    new_sections: list[Section] = []
    for section in note.sections:
        new_lines: list[str] = []
        for line in section.lines:
            match = _OPEN_TASK_RE.match(line)
            if match is not None:
                seen += 1
                if seen == n:
                    new_lines.append(f"- [x] {match.group(1)}")
                    continue
            new_lines.append(line)
        new_sections.append(
            Section(heading=section.heading, lines=tuple(new_lines))
        )
    return Note(sections=tuple(new_sections), ends_with_newline=note.ends_with_newline)
