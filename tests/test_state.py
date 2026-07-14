"""Tests for od.state — sticky state under vault_root."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from od import state as state_mod
from od.state import (
    State,
    StateError,
    StickyExpired,
    clear_sticky,
    get,
    set_sticky,
    set_vault,
    swap_sticky,
)


@pytest.fixture
def vault_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated HOME + vault_root so state lands under a temp collection."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    root = tmp_path / "vaults"
    root.mkdir()
    global_dir = home / ".config" / "od"
    global_dir.mkdir(parents=True)
    (global_dir / "config.toml").write_text(
        f'vault_root = "{root}"\n',
        encoding="utf-8",
    )
    return root


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> date:
    today = date(2026, 7, 14)
    monkeypatch.setattr(state_mod, "_today", lambda: today)
    return today


def test_missing_file_is_empty_state(vault_root: Path, fixed_today: date) -> None:
    st = get()
    assert st == State(
        active_vault=None,
        sticky_target=None,
        sticky_prev=None,
        sticky_set_on=None,
    )
    assert not (vault_root / "od-state.toml").exists()


def test_set_vault_persists(vault_root: Path, fixed_today: date) -> None:
    set_vault("draeician")
    st = get()
    assert st.active_vault == "draeician"
    text = (vault_root / "od-state.toml").read_text(encoding="utf-8")
    assert "draeician" in text


def test_set_sticky_sets_today_and_prev(
    vault_root: Path, fixed_today: date
) -> None:
    set_sticky("todo")
    st = get()
    assert st.sticky_target == "todo"
    assert st.sticky_set_on == fixed_today
    assert st.sticky_prev is None

    set_sticky("personal updates")
    st = get()
    assert st.sticky_target == "personal updates"
    assert st.sticky_prev == "todo"
    assert st.sticky_set_on == fixed_today


def test_swap_sticky(vault_root: Path, fixed_today: date) -> None:
    set_sticky("a")
    set_sticky("b")
    swap_sticky()
    st = get()
    assert st.sticky_target == "a"
    assert st.sticky_prev == "b"


def test_clear_sticky_keeps_prev_for_swap(
    vault_root: Path, fixed_today: date
) -> None:
    set_sticky("todo")
    clear_sticky()
    st = get()
    assert st.sticky_target is None
    assert st.sticky_set_on is None
    assert st.sticky_prev == "todo"


def test_expired_sticky_raises_on_get(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state_mod, "_today", lambda: date(2026, 7, 14))
    set_sticky("todo")
    monkeypatch.setattr(state_mod, "_today", lambda: date(2026, 7, 15))
    with pytest.raises(StickyExpired) as excinfo:
        get()
    assert excinfo.value.target == "todo"
    assert excinfo.value.set_on == date(2026, 7, 14)
    # Vault-only callers may skip the freshness check.
    st = get(check_sticky=False)
    assert st.sticky_target == "todo"
    assert st.active_vault is None or st.active_vault is not None


def test_expired_sticky_raises_on_swap(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state_mod, "_today", lambda: date(2026, 7, 14))
    set_sticky("todo")
    set_sticky("other")
    monkeypatch.setattr(state_mod, "_today", lambda: date(2026, 7, 15))
    with pytest.raises(StickyExpired):
        swap_sticky()


def test_clear_sticky_works_when_expired(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state_mod, "_today", lambda: date(2026, 7, 14))
    set_sticky("todo")
    monkeypatch.setattr(state_mod, "_today", lambda: date(2026, 7, 15))
    clear_sticky()
    st = get()
    assert st.sticky_target is None


def test_set_vault_works_when_sticky_expired(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state_mod, "_today", lambda: date(2026, 7, 14))
    set_sticky("todo")
    monkeypatch.setattr(state_mod, "_today", lambda: date(2026, 7, 15))
    set_vault("riddell")
    text = (vault_root / "od-state.toml").read_text(encoding="utf-8")
    assert 'active_vault = "riddell"' in text
    with pytest.raises(StickyExpired):
        get()


def test_atomic_write_replaces_file(
    vault_root: Path, fixed_today: date
) -> None:
    set_vault("one")
    set_vault("two")
    path = vault_root / "od-state.toml"
    assert path.is_file()
    assert not path.with_name("od-state.toml.tmp").exists()
    assert get().active_vault == "two"


def test_empty_names_raise(vault_root: Path, fixed_today: date) -> None:
    with pytest.raises(StateError):
        set_vault("")
    with pytest.raises(StateError):
        set_sticky("  ")


def test_missing_vault_root_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    (home / ".config" / "od").mkdir(parents=True)
    (home / ".config" / "od" / "config.toml").write_text("", encoding="utf-8")
    with pytest.raises(StateError, match="vault_root"):
        get()
