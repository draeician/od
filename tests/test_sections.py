"""Tests for od.sections — pure daily-note markdown helpers."""

from __future__ import annotations

from datetime import datetime

import pytest

from od.sections import (
    DuplicateHeadingError,
    Note,
    Section,
    TaskIndexError,
    UnknownStyleError,
    add_section,
    append_to_section,
    mark_done,
    open_tasks,
    parse,
    render,
)


# ---------------------------------------------------------------------------
# Round-trip fidelity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n",
        "preamble only\n",
        "# solo\n",
        "# solo",
        "# a\nline\n",
        "# a\n\n# b\n",
        "front\n# a\nx\n# b\ny\n",
        "# a\n- [ ] one\n- [x] two\n",
        "# a\n- 2026-07-14 09:00 :hello\n",
        "# a\n```\ncode\nline\n```\n",
        "# a\n## not an h1\nstill body\n",
        "# title with: colons\n- item\n",
    ],
)
def test_render_parse_round_trip(text: str) -> None:
    assert render(parse(text)) == text


def test_parse_splits_only_on_h1() -> None:
    note = parse("# top\n## sub\nbody\n# two\n")
    assert len(note.sections) == 2
    assert note.sections[0].heading == "top"
    assert note.sections[0].lines == ("## sub", "body")
    assert note.sections[1].heading == "two"
    assert note.sections[1].lines == ()


def test_parse_preamble_before_first_h1() -> None:
    note = parse("meta\n# a\nx\n")
    assert note.sections[0] == Section(heading=None, lines=("meta",))
    assert note.sections[1] == Section(heading="a", lines=("x",))


# ---------------------------------------------------------------------------
# add_section
# ---------------------------------------------------------------------------


def test_add_section_appends_empty_h1() -> None:
    note = parse("# a\nx\n")
    out = add_section(note, "b")
    assert out.sections[-1] == Section(heading="b", lines=())
    # Blank line separates consecutive H1s.
    assert render(out) == "# a\nx\n\n# b\n"


def test_add_section_duplicate_raises() -> None:
    note = parse("# a\n")
    with pytest.raises(DuplicateHeadingError):
        add_section(note, "a")


# ---------------------------------------------------------------------------
# append_to_section + styles
# ---------------------------------------------------------------------------


def test_append_plain_explicit() -> None:
    note = parse("# a\n")
    out = append_to_section(note, "a", "hello", style="plain")
    assert render(out) == "# a\n- hello\n"


def test_append_todo_explicit() -> None:
    note = parse("# a\n")
    out = append_to_section(note, "a", "ship it", style="todo")
    assert render(out) == "# a\n- [ ] ship it\n"


def test_append_log_uses_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return datetime(2026, 7, 14, 15, 30)

    monkeypatch.setattr("od.sections.datetime", FixedDateTime)
    note = parse("# a\n")
    out = append_to_section(note, "a", "deployed", style="log")
    assert render(out) == "# a\n- 2026-07-14 15:30 :deployed\n"


def test_append_code_fenced_block() -> None:
    note = parse("# a\n")
    out = append_to_section(note, "a", "echo hi\necho bye", style="code")
    assert render(out) == "# a\n```\necho hi\necho bye\n```\n"


def test_append_unknown_heading_creates_section() -> None:
    note = parse("# a\nx\n")
    out = append_to_section(note, "new", "item", style="plain")
    assert render(out) == "# a\nx\n\n# new\n- item\n"


def test_blank_line_between_headers_on_switch() -> None:
    """p → c → p keeps one # p and blanks between H1 sections."""
    note = parse("")
    note = append_to_section(note, "p", "first", style="plain")
    note = append_to_section(note, "c", "df -h", style="code")
    note = append_to_section(note, "p", "second", style="plain")
    text = render(note)
    assert text == (
        "# p\n"
        "- first\n"
        "- second\n"
        "\n"
        "# c\n"
        "```\n"
        "df -h\n"
        "```\n"
    )
    assert sum(1 for s in note.sections if s.heading == "p") == 1


def test_append_unknown_style_raises() -> None:
    note = parse("# a\n")
    with pytest.raises(UnknownStyleError):
        append_to_section(note, "a", "x", style="nope")


def test_auto_style_detects_todo() -> None:
    note = parse("# a\n- [ ] existing\n")
    out = append_to_section(note, "a", "next", style="auto")
    assert "- [ ] next" in render(out)


def test_auto_style_detects_log(monkeypatch: pytest.MonkeyPatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return datetime(2026, 7, 14, 12, 0)

    monkeypatch.setattr("od.sections.datetime", FixedDateTime)
    note = parse("# a\n- 2026-01-01 10:00 :old\n")
    out = append_to_section(note, "a", "new", style="auto")
    assert "- 2026-07-14 12:00 :new" in render(out)


def test_auto_style_empty_section_is_plain() -> None:
    note = parse("# a\n")
    out = append_to_section(note, "a", "item", style="auto")
    assert render(out) == "# a\n- item\n"


def test_auto_style_done_tasks_still_todo() -> None:
    note = parse("# a\n- [x] finished\n")
    out = append_to_section(note, "a", "more", style="auto")
    assert "- [ ] more" in render(out)


# ---------------------------------------------------------------------------
# open_tasks / mark_done
# ---------------------------------------------------------------------------


def test_open_tasks_document_order() -> None:
    note = parse("# a\n- [ ] first\n- [x] skip\n- [ ] second\n# b\n- [ ] third\n")
    tasks = open_tasks(note)
    assert [t.index for t in tasks] == [1, 2, 3]
    assert [t.text for t in tasks] == ["first", "second", "third"]
    assert [t.heading for t in tasks] == ["a", "a", "b"]


def test_mark_done_nth_open_task() -> None:
    note = parse("# a\n- [ ] first\n- [x] already\n- [ ] second\n")
    out = mark_done(note, 2)
    assert render(out) == "# a\n- [ ] first\n- [x] already\n- [x] second\n"
    assert open_tasks(out)[0].text == "first"
    assert len(open_tasks(out)) == 1


def test_mark_done_out_of_range_raises() -> None:
    note = parse("# a\n- [ ] only\n")
    with pytest.raises(TaskIndexError):
        mark_done(note, 2)
    with pytest.raises(TaskIndexError):
        mark_done(note, 0)


def test_mark_done_preserves_unrelated_content() -> None:
    src = "# a\nintro\n- [ ] task\n```\ncode\n```\n"
    out = mark_done(parse(src), 1)
    assert render(out) == "# a\nintro\n- [x] task\n```\ncode\n```\n"


# ---------------------------------------------------------------------------
# Purity / immutability
# ---------------------------------------------------------------------------


def test_transforms_return_new_note() -> None:
    original = parse("# a\n- [ ] t\n")
    rendered = render(original)
    append_to_section(original, "a", "x", style="plain")
    mark_done(original, 1)
    add_section(original, "b")
    assert render(original) == rendered


def test_no_io_imports_in_public_surface() -> None:
    """Smoke: module stays stdlib-only and does not expose I/O helpers."""
    import od.sections as mod

    assert not hasattr(mod, "open")
    assert not hasattr(mod, "Path")
