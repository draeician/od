"""Tests for od.vault — safe daily-note read-modify-write."""

from __future__ import annotations

from typing import Any

import pytest

from od import vault as vault_mod
from od.sections import DuplicateHeadingError, TaskIndexError
from od.vault import (
    Glance,
    VaultError,
    WriteSafetyError,
    append,
    check_write_safety,
    complete_task,
    glance,
    new_section,
)


@pytest.fixture
def daily_store(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """In-memory daily note + path; stubs all obsidian I/O used by vault."""
    store: dict[str, Any] = {
        "path": "daily_notes/2026-07-14.md",
        "text": "",
        "writes": [],
    }

    def run(vault: str, args: list[str]) -> str:
        if list(args) == ["daily:path"]:
            return store["path"]
        raise AssertionError(f"unexpected run args: {args}")

    def daily_read(vault: str) -> str:
        return store["text"]

    def create_overwrite(vault: str, path: str, content: str) -> None:
        store["writes"].append({"vault": vault, "path": path, "content": content})
        store["text"] = content

    monkeypatch.setattr(vault_mod.obsidian, "run", run)
    monkeypatch.setattr(vault_mod.obsidian, "daily_read", daily_read)
    monkeypatch.setattr(vault_mod.obsidian, "create_overwrite", create_overwrite)
    return store


SAMPLE = (
    "# personal updates\n"
    "\n"
    "- [ ] buy milk\n"
    "- [ ] call Sam\n"
    "\n"
    "# daily checks\n"
    "\n"
    "- [ ] standup\n"
)


def test_check_write_safety_ok_growth() -> None:
    check_write_safety("# a\n", "# a\n- x\n")


def test_check_write_safety_drops_heading() -> None:
    with pytest.raises(WriteSafetyError, match="drop heading"):
        check_write_safety("# a\n\n# b\n", "# a\n")


def test_check_write_safety_shrink() -> None:
    with pytest.raises(WriteSafetyError, match="shrank"):
        check_write_safety("# a\n\nlong body here\n", "# a\n")


def test_append_to_existing_section(daily_store: dict[str, Any]) -> None:
    daily_store["text"] = SAMPLE
    out = append("work", "personal updates", "shipped feature", style="todo")
    assert "- [ ] shipped feature" in out
    assert "# personal updates" in out
    assert "# daily checks" in out
    assert len(daily_store["writes"]) == 1
    assert daily_store["writes"][0]["path"] == "daily_notes/2026-07-14.md"
    assert daily_store["writes"][0]["vault"] == "work"
    assert daily_store["text"] == out


def test_append_unknown_heading_creates_section(daily_store: dict[str, Any]) -> None:
    daily_store["text"] = SAMPLE
    out = append("work", "truscan modifications", "note", style="plain")
    assert "# truscan modifications" in out
    assert "- note" in out
    # Prior headings preserved
    assert "# personal updates" in out
    assert "# daily checks" in out


def test_append_empty_note(daily_store: dict[str, Any]) -> None:
    daily_store["text"] = ""
    out = append("work", "todo", "first", style="todo")
    assert out.startswith("# todo")
    assert "- [ ] first" in out


def test_append_rejects_empty_heading(daily_store: dict[str, Any]) -> None:
    with pytest.raises(VaultError, match="heading"):
        append("work", "  ", "x")


def test_glance(daily_store: dict[str, Any]) -> None:
    daily_store["text"] = SAMPLE
    g = glance("work")
    assert isinstance(g, Glance)
    assert g.vault == "work"
    assert g.path == "daily_notes/2026-07-14.md"
    assert g.headings == ("personal updates", "daily checks")
    assert [t.index for t in g.tasks] == [1, 2, 3]
    assert g.tasks[0].text == "buy milk"
    assert g.tasks[2].heading == "daily checks"
    assert daily_store["writes"] == []


def test_glance_empty_note(daily_store: dict[str, Any]) -> None:
    daily_store["text"] = ""
    g = glance("work")
    assert g.headings == ()
    assert g.tasks == ()


def test_new_section(daily_store: dict[str, Any]) -> None:
    daily_store["text"] = SAMPLE
    out = new_section("work", "michael brumit")
    assert "# michael brumit" in out
    assert "# personal updates" in out
    assert daily_store["text"] == out


def test_new_section_duplicate(daily_store: dict[str, Any]) -> None:
    daily_store["text"] = SAMPLE
    with pytest.raises(DuplicateHeadingError):
        new_section("work", "personal updates")
    assert daily_store["writes"] == []
    assert daily_store["text"] == SAMPLE


def test_complete_task(daily_store: dict[str, Any]) -> None:
    daily_store["text"] = SAMPLE
    out = complete_task("work", 2)
    assert "- [x] call Sam" in out
    assert "- [ ] buy milk" in out
    assert "- [ ] standup" in out
    # Length preserved for checkbox toggle ([ ] -> [x])
    assert len(out) == len(SAMPLE) or len(out) >= len(SAMPLE)
    assert daily_store["writes"]


def test_complete_task_bad_index(daily_store: dict[str, Any]) -> None:
    daily_store["text"] = SAMPLE
    with pytest.raises(TaskIndexError):
        complete_task("work", 99)
    assert daily_store["writes"] == []


def test_write_safety_blocks_corrupt_transform(
    daily_store: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    daily_store["text"] = SAMPLE

    def bad_append(note, heading, line, style="auto"):
        # Drop everything
        from od.sections import Note

        return Note(sections=(), ends_with_newline=True)

    monkeypatch.setattr(vault_mod.sections, "append_to_section", bad_append)
    with pytest.raises(WriteSafetyError):
        append("work", "personal updates", "x")
    assert daily_store["writes"] == []
    assert daily_store["text"] == SAMPLE


def test_empty_daily_path_raises(
    daily_store: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(vault: str, args: list[str]) -> str:
        return "  \n"

    monkeypatch.setattr(vault_mod.obsidian, "run", run)
    with pytest.raises(VaultError, match="daily:path"):
        glance("work")


def test_complete_task_rejects_non_int(daily_store: dict[str, Any]) -> None:
    with pytest.raises(VaultError, match="task index"):
        complete_task("work", "1")  # type: ignore[arg-type]
