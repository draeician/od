"""vault.py — safe read-modify-write orchestration

Purpose:
    The write-safety layer: daily_read -> sections transform -> sanity
    check -> create_overwrite.

Public:
    append(vault, heading, text, style=auto)
    glance(vault) -> Glance
    new_section(vault, heading)
    complete_task(vault, n)

Invariants:
    Never write back a note that lost content — post-transform check
    verifies all prior headings present and content not shrunk except by
    explicit edit; violation raises WriteSafetyError and nothing is
    written; new-section appends are the only blind appends.

Depends on:
    obsidian, sections.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from od import obsidian, sections
from od.sections import Note, Task

__all__ = [
    "VaultError",
    "WriteSafetyError",
    "Glance",
    "append",
    "glance",
    "new_section",
    "complete_task",
]


class VaultError(Exception):
    """Raised when a vault read/write orchestration step fails."""


class WriteSafetyError(VaultError):
    """Raised when a transform would drop headings or shrink content.

    Callers must not write; the daily note is left unchanged.
    """


@dataclass(frozen=True)
class Glance:
    """Today-at-a-glance snapshot for a vault."""

    vault: str
    path: str
    headings: tuple[str, ...]
    tasks: tuple[Task, ...]


def _daily_path(vault: str) -> str:
    path = obsidian.run(vault, ["daily:path"]).strip()
    if not path:
        raise VaultError(
            "daily:path returned empty; is Daily notes configured in Obsidian?"
        )
    return path


def _headings(note: Note) -> list[str]:
    return [s.heading for s in note.sections if s.heading is not None]


def check_write_safety(original: str, modified: str) -> None:
    """Abort if *modified* drops H1s or is shorter than *original*.

    Public for unit tests; production callers use :func:`_rmw`.
    """
    orig_note = sections.parse(original)
    mod_note = sections.parse(modified)
    orig_heads = _headings(orig_note)
    mod_heads = set(_headings(mod_note))
    missing = [h for h in orig_heads if h not in mod_heads]
    if missing:
        raise WriteSafetyError(
            "refusing write: transform would drop heading(s): "
            + ", ".join(repr(h) for h in missing)
        )
    if len(modified) < len(original):
        raise WriteSafetyError(
            "refusing write: transform shrank note content "
            f"({len(original)} -> {len(modified)} chars)"
        )


def _rmw(vault: str, transform: Callable[[Note], Note]) -> str:
    """Read daily note, apply *transform*, safety-check, overwrite.

    Returns the written markdown text.
    """
    path = _daily_path(vault)
    original = obsidian.daily_read(vault)
    note = sections.parse(original)
    new_note = transform(note)
    modified = sections.render(new_note)
    check_write_safety(original, modified)
    obsidian.create_overwrite(vault, path, modified)
    return modified


def append(
    vault: str,
    heading: str,
    text: str,
    style: str = "auto",
) -> str:
    """Append *text* under *heading* in today's daily note (RMW).

    Unknown headings create a new H1 at the end of the file. *style* is
    ``auto|todo|log|plain|code`` (see ``sections.append_to_section``).

    Returns:
        The full modified note text after a successful write.
    """
    if not heading or not str(heading).strip():
        raise VaultError("heading must be non-empty")
    if text is None:
        raise VaultError("text must not be None")

    heading = str(heading).strip()

    def _transform(note: Note) -> Note:
        return sections.append_to_section(note, heading, text, style=style)

    return _rmw(vault, _transform)


def glance(vault: str) -> Glance:
    """Return today's outline (H1 headings) and open tasks for *vault*."""
    path = _daily_path(vault)
    text = obsidian.daily_read(vault)
    note = sections.parse(text)
    tasks = tuple(sections.open_tasks(note))
    return Glance(
        vault=vault,
        path=path,
        headings=tuple(_headings(note)),
        tasks=tasks,
    )


def new_section(vault: str, heading: str) -> str:
    """Create a new empty H1 section in today's daily note.

    Raises ``sections.DuplicateHeadingError`` if the heading already
    exists. Uses the RMW path (not a blind append) so write-safety still
    applies; a pure append of a new H1 would also be allowed by the
    module contract but is unnecessary when RMW is available.

    Returns:
        The full modified note text after a successful write.
    """
    if not heading or not str(heading).strip():
        raise VaultError("heading must be non-empty")
    heading = str(heading).strip()

    def _transform(note: Note) -> Note:
        return sections.add_section(note, heading)

    return _rmw(vault, _transform)


def complete_task(vault: str, n: int) -> str:
    """Mark open task *n* (1-based) done in today's daily note (RMW).

    Returns:
        The full modified note text after a successful write.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise VaultError(f"task index must be an int, got {type(n).__name__}")

    def _transform(note: Note) -> Note:
        return sections.mark_done(note, n)

    return _rmw(vault, _transform)
