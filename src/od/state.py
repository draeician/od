"""state.py — sticky state

Purpose:
    Read/write <vault_root>/od-state.toml: active_vault, sticky_target,
    sticky_prev, sticky_set_on.

Public:
    get() -> State
    set_vault(name)
    set_sticky(target)
    swap_sticky()
    clear_sticky()

Invariants:
    Sticky reads compare sticky_set_on to today — expired sticky raises
    StickyExpired (caller decides messaging); writes are atomic (temp file
    + rename); missing file = empty state, never an error.

Depends on:
    config (for vault_root), stdlib.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from od import config

__all__ = [
    "StateError",
    "StickyExpired",
    "State",
    "get",
    "set_vault",
    "set_sticky",
    "swap_sticky",
    "clear_sticky",
]


class StateError(Exception):
    """Base error for sticky-state operations."""


class StickyExpired(StateError):
    """Sticky target was set on a previous day and must be re-set.

    Callers (cli) format user-facing copy; this carries target and date.
    """

    def __init__(self, target: str, set_on: date) -> None:
        self.target = target
        self.set_on = set_on
        super().__init__(
            f"sticky {target!r} expired (set on {set_on.isoformat()}); "
            f"re-set with `od = {target}`"
        )


@dataclass(frozen=True)
class State:
    """In-memory view of ``<vault_root>/od-state.toml``."""

    active_vault: str | None
    sticky_target: str | None
    sticky_prev: str | None
    sticky_set_on: date | None


def _today() -> date:
    """Current local date (patchable in tests)."""
    return date.today()


def _state_path() -> Path:
    """Resolve ``<vault_root>/od-state.toml`` via config."""
    cfg = config.load(None, {})
    if not cfg.vault_root:
        raise StateError(
            "vault_root is not set; cannot read/write state "
            "(set vault_root in ~/.config/od/config.toml)"
        )
    return Path(cfg.vault_root).expanduser() / "od-state.toml"


def _empty_data() -> dict[str, Any]:
    return {
        "active_vault": None,
        "sticky_target": None,
        "sticky_prev": None,
        "sticky_set_on": None,
    }


def _read_raw() -> dict[str, Any]:
    """Load state file; missing file → empty state (never an error)."""
    path = _state_path()
    if not path.is_file():
        return _empty_data()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise StateError(f"cannot read state file {path}: {exc}") from exc
    if not raw.strip():
        return _empty_data()
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise StateError(f"invalid TOML in state file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise StateError(f"state file root must be a table: {path}")
    return _normalize_raw(data)


def _normalize_raw(data: dict[str, Any]) -> dict[str, Any]:
    out = _empty_data()
    for key in out:
        if key not in data:
            continue
        value = data[key]
        if value is None or value == "":
            out[key] = None
        else:
            out[key] = str(value)
    return out


def _parse_date(value: str | None) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise StateError(
            f"invalid sticky_set_on date {value!r}; expected YYYY-MM-DD"
        ) from exc


def _to_state(data: dict[str, Any]) -> State:
    return State(
        active_vault=data.get("active_vault"),
        sticky_target=data.get("sticky_target"),
        sticky_prev=data.get("sticky_prev"),
        sticky_set_on=_parse_date(data.get("sticky_set_on")),
    )


def _check_sticky_fresh(state: State) -> None:
    """Raise StickyExpired when a sticky target is set for a past day."""
    if not state.sticky_target:
        return
    if state.sticky_set_on is None:
        raise StickyExpired(state.sticky_target, date.min)
    if state.sticky_set_on != _today():
        raise StickyExpired(state.sticky_target, state.sticky_set_on)


def _write_raw(data: dict[str, Any]) -> None:
    """Atomically write state via temp file + os.replace."""
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StateError(
            f"cannot create state directory {path.parent}: {exc}"
        ) from exc

    payload = {
        "active_vault": data.get("active_vault"),
        "sticky_target": data.get("sticky_target"),
        "sticky_prev": data.get("sticky_prev"),
        "sticky_set_on": data.get("sticky_set_on"),
    }
    text = config.emit_toml(payload)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise StateError(f"cannot write state file {path}: {exc}") from exc


def get(*, check_sticky: bool = True) -> State:
    """Return current state.

    Missing state file yields an empty State. When *check_sticky* is True
    (default) and a sticky target is set with ``sticky_set_on`` not today,
    raise ``StickyExpired``. Active vault does not expire.

    Pass ``check_sticky=False`` for vault-only operations (glance, list,
    etc.) that must not fail solely because yesterday's sticky expired.
    """
    state = _to_state(_read_raw())
    if check_sticky:
        _check_sticky_fresh(state)
    return state


def set_vault(name: str) -> None:
    """Persist ``active_vault``. Does not touch sticky fields."""
    if not name or not str(name).strip():
        raise StateError("vault name must be non-empty")
    data = _read_raw()
    data["active_vault"] = str(name).strip()
    _write_raw(data)


def set_sticky(target: str) -> None:
    """Set sticky target for today; previous target becomes sticky_prev."""
    if not target or not str(target).strip():
        raise StateError("sticky target must be non-empty")
    target = str(target).strip()
    data = _read_raw()
    previous = data.get("sticky_target")
    if previous and previous != target:
        data["sticky_prev"] = previous
    data["sticky_target"] = target
    data["sticky_set_on"] = _today().isoformat()
    _write_raw(data)


def swap_sticky() -> None:
    """Swap sticky_target with sticky_prev; refresh sticky_set_on to today.

    Raises StickyExpired if the current sticky is set but expired.
    """
    data = _read_raw()
    state = _to_state(data)
    _check_sticky_fresh(state)

    current = data.get("sticky_target")
    previous = data.get("sticky_prev")
    data["sticky_target"] = previous
    data["sticky_prev"] = current
    if data["sticky_target"]:
        data["sticky_set_on"] = _today().isoformat()
    else:
        data["sticky_set_on"] = None
    _write_raw(data)


def clear_sticky() -> None:
    """Clear sticky_target and sticky_set_on (works even when expired).

    Leaves sticky_prev so a later swap can restore the last target.
    """
    data = _read_raw()
    previous = data.get("sticky_target")
    if previous:
        data["sticky_prev"] = previous
    data["sticky_target"] = None
    data["sticky_set_on"] = None
    _write_raw(data)
