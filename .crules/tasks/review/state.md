# Task: state.py — sticky state

Wave: 2

## Module
`src/od/state.py`

## Purpose
Read/write `<vault_root>/od-state.toml`: `active_vault`, `sticky_target`,
`sticky_prev`, `sticky_set_on`.

## Public Interface
- `get() -> State`
- `set_vault(name)`
- `set_sticky(target)`
- `swap_sticky()`
- `clear_sticky()`

## Acceptance Criteria
- [x] Sticky reads compare `sticky_set_on` to today — expired sticky raises `StickyExpired` (caller decides messaging).
- [x] Writes are atomic (temp file + rename).
- [x] Missing file = empty state, never an error.
- [x] Depends only on `config` (for `vault_root`) and stdlib.
- [x] Tests added in `tests/test_state.py`.

## Depends On
config (for `vault_root`), stdlib.

## Coder Notes

- **File:** `<vault_root>/od-state.toml` via `config.load(None, {})` for
  `vault_root`; missing file → empty `State`.
- **`get()`:** raises `StickyExpired` when `sticky_target` set and
  `sticky_set_on != today` (or date missing). Active vault never expires.
- **Mutators:** `set_vault` / `set_sticky` / `clear_sticky` use raw read so
  vault can change and sticky can clear even when expired; `swap_sticky`
  enforces freshness then swaps and refreshes `sticky_set_on` to today.
- **Atomic write:** write `od-state.toml.tmp` then `os.replace`; TOML via
  `config.emit_toml`.
- **Verify:** `pytest tests/test_state.py -v` → 12 passed.
- **No version bump** (hold until release).
- Wave 2 remaining: `obsidian`, `entities`.
