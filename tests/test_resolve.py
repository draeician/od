"""Tests for od.resolve — pure argv → Command classification."""

from __future__ import annotations

from datetime import date

import pytest

from od.config import Config
from od.resolve import (
    AmbiguousPrefix,
    Append,
    ClearSticky,
    Done,
    Glance,
    ListVaults,
    New,
    NoTargetError,
    SetSticky,
    SetVault,
    ShowConfig,
    ShowSticky,
    SwapSticky,
    Todo,
    UsageError,
    Who,
    expand_target,
    match_reserved,
    resolve,
)
from od.state import State


def _cfg(aliases: dict[str, str] | None = None) -> Config:
    data: dict = {
        "vault_root": None,
        "vaults": {"default": None},
        "aliases": dict(aliases or {}),
        "entities": {"dir": "entities"},
    }
    return Config(data=data)


def _state(
    *,
    sticky: str | None = None,
    vault: str | None = "work",
) -> State:
    return State(
        active_vault=vault,
        sticky_target=sticky,
        sticky_prev=None,
        sticky_set_on=date(2026, 7, 14) if sticky else None,
    )


def test_empty_is_glance() -> None:
    assert resolve([], _cfg(), _state()) == Glance()


def test_match_reserved_exact_and_prefix() -> None:
    assert match_reserved("todo") == "todo"
    assert match_reserved("vaults") == "vaults"
    assert match_reserved("v") == "vaults"
    assert match_reserved("d") == "done"
    assert match_reserved("n") == "new"
    assert match_reserved("w") == "who"
    assert match_reserved("c") == "config"
    assert match_reserved("to") == "todo"
    assert match_reserved("xyz") is None


def test_match_reserved_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    import od.resolve as resolve_mod

    # Current RESERVED_WORDS have no ambiguous prefixes; inject a set that does.
    monkeypatch.setattr(
        resolve_mod,
        "RESERVED_WORDS",
        frozenset({"task", "take", "todo"}),
    )
    with pytest.raises(AmbiguousPrefix) as ei:
        match_reserved("ta")
    assert ei.value.prefix == "ta"
    assert ei.value.candidates == ("take", "task")
    assert match_reserved("") is None


def test_reserved_commands() -> None:
    cfg, st = _cfg(), _state()
    assert resolve(["todo"], cfg, st) == Todo()
    assert resolve(["to"], cfg, st) == Todo()  # prefix
    assert resolve(["config"], cfg, st) == ShowConfig()
    assert resolve(["vaults"], cfg, st) == ListVaults()
    assert resolve(["v"], cfg, st) == ListVaults()
    assert resolve(["v", "draeician"], cfg, st) == SetVault(name="draeician")
    assert resolve(["vaults", "x"], cfg, st) == SetVault(name="x")
    assert resolve(["done", "3"], cfg, st) == Done(index=3)
    assert resolve(["new", "daily checks"], cfg, st) == New(heading="daily checks")
    assert resolve(["who", "michael"], cfg, st) == Who(name="michael")


def test_reserved_usage_errors() -> None:
    cfg, st = _cfg(), _state()
    with pytest.raises(UsageError):
        resolve(["todo", "extra"], cfg, st)
    with pytest.raises(UsageError):
        resolve(["done"], cfg, st)
    with pytest.raises(UsageError):
        resolve(["done", "x"], cfg, st)
    with pytest.raises(UsageError):
        resolve(["done", "0"], cfg, st)
    with pytest.raises(UsageError):
        resolve(["new"], cfg, st)
    with pytest.raises(UsageError):
        resolve(["who", "a", "b"], cfg, st)
    with pytest.raises(UsageError):
        resolve(["vaults", "a", "b"], cfg, st)


def test_sticky_grammar() -> None:
    cfg = _cfg({"t": "truscan modifications"})
    st = _state()
    assert resolve(["="], cfg, st) == ShowSticky()
    assert resolve(["=", "-"], cfg, st) == SwapSticky()
    assert resolve(["=", "off"], cfg, st) == ClearSticky()
    assert resolve(["=", "todo"], cfg, st) == SetSticky(target="todo")
    # Alias expanded when setting sticky
    assert resolve(["=", "t"], cfg, st) == SetSticky(
        target="truscan modifications"
    )
    # Glued form
    assert resolve(["=off"], cfg, st) == ClearSticky()
    assert resolve(["=todo"], cfg, st) == SetSticky(target="todo")
    with pytest.raises(UsageError):
        resolve(["=", "a", "b"], cfg, st)


def test_exact_alias_beats_reserved_prefix() -> None:
    """Alias ``t`` must not resolve to ``todo`` when used as a target."""
    cfg = _cfg({"t": "truscan modifications"})
    st = _state(sticky="personal updates")
    cmd = resolve(["t", "shipped"], cfg, st)
    assert cmd == Append(
        target="truscan modifications",
        text="shipped",
        style="auto",
        via_sticky=False,
    )
    # Bare ``todo`` still the reserved verb
    assert resolve(["todo"], cfg, st) == Todo()


def test_one_word_sticky_append() -> None:
    cfg = _cfg({"t": "truscan modifications"})
    st = _state(sticky="t")
    cmd = resolve(["hello world"], cfg, st)
    assert cmd == Append(
        target="truscan modifications",
        text="hello world",
        style="auto",
        via_sticky=True,
    )


def test_one_word_no_sticky_errors() -> None:
    with pytest.raises(NoTargetError):
        resolve(["hello"], _cfg(), _state(sticky=None))


def test_two_word_explicit_target() -> None:
    cfg = _cfg({"m": "michael brumit"})
    st = _state(sticky="ignored")
    cmd = resolve(["m", "discussed migration"], cfg, st)
    assert isinstance(cmd, Append)
    assert cmd.target == "michael brumit"
    assert cmd.text == "discussed migration"
    assert cmd.via_sticky is False
    # Free heading (not an alias)
    cmd2 = resolve(["daily checks", "ok"], cfg, st)
    assert cmd2 == Append(
        target="daily checks",
        text="ok",
        style="auto",
        via_sticky=False,
    )


def test_piped_one_word_is_code_target() -> None:
    cfg = _cfg({"t": "truscan modifications"})
    st = _state(sticky=None)
    cmd = resolve(["t"], cfg, st, stdin_piped=True)
    assert cmd == Append(
        target="truscan modifications",
        text=None,
        style="code",
        via_sticky=False,
    )
    # Free heading with pipe
    cmd2 = resolve(["personal updates"], cfg, st, stdin_piped=True)
    assert cmd2 == Append(
        target="personal updates",
        text=None,
        style="code",
        via_sticky=False,
    )


def test_piped_reserved_still_reserved() -> None:
    assert resolve(["todo"], _cfg(), _state(), stdin_piped=True) == Todo()


def test_too_many_args() -> None:
    with pytest.raises(UsageError, match="too many"):
        resolve(["a", "b", "c"], _cfg(), _state(sticky="x"))


def test_expand_target() -> None:
    cfg = _cfg({"t": "truscan modifications"})
    assert expand_target("t", cfg) == "truscan modifications"
    assert expand_target("other", cfg) == "other"


def test_prefix_v_with_name_sets_vault() -> None:
    cmd = resolve(["v", "riddell"], _cfg(), _state())
    assert cmd == SetVault(name="riddell")
