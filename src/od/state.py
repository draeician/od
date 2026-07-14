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
